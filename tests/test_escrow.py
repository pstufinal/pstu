"""
Integration tests for Escrow functionality.
"""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.escrow import EscrowPayment
from app.models.transaction import IdempotencyRecord, LedgerEntry, Transaction
from app.models.user import User
from app.models.wallet import Wallet

client = TestClient(app)

ALICE_USERNAME = "escrow_test_alice"
BOB_USERNAME = "escrow_test_bob"
INITIAL_BALANCE = Decimal("100000.00")

def cleanup_db(db: Session):
    # Ensure ESCROW_HOLD exists (normally created in lifespan, but test DB might be fresh)
    if not db.query(User).filter_by(username="ESCROW_HOLD").first():
        escrow_sys = User(username="ESCROW_HOLD", hashed_password=hash_password("test"))
        db.add(escrow_sys)
        db.flush()
        sys_wallet = Wallet(user_id=escrow_sys.id, balance=Decimal("0.00"))
        db.add(sys_wallet)

    users_to_delete = db.query(User).filter(User.username.in_([ALICE_USERNAME, BOB_USERNAME])).all()
    user_ids = [u.id for u in users_to_delete]
    if user_ids:
        db.query(EscrowPayment).filter(
            (EscrowPayment.buyer_user_id.in_(user_ids)) | (EscrowPayment.seller_user_id.in_(user_ids))
        ).delete(synchronize_session=False)
        wallets = db.query(Wallet).filter(Wallet.user_id.in_(user_ids)).all()
        wallet_ids = [w.id for w in wallets]
        if wallet_ids:
            txs = db.query(Transaction).filter(
                (Transaction.sender_wallet_id.in_(wallet_ids)) | 
                (Transaction.recipient_wallet_id.in_(wallet_ids))
            ).all()
            tx_ids = [tx.id for tx in txs]
            if tx_ids:
                db.query(LedgerEntry).filter(LedgerEntry.transaction_id.in_(tx_ids)).delete(synchronize_session=False)
                db.query(Transaction).filter(Transaction.id.in_(tx_ids)).delete(synchronize_session=False)
            db.query(Wallet).filter(Wallet.id.in_(wallet_ids)).delete(synchronize_session=False)
        db.query(IdempotencyRecord).filter(IdempotencyRecord.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
    db.commit()


@pytest.fixture(autouse=True)
def setup_teardown():
    # We rely on TestClient to trigger lifespan, but to be safe:
    Base.metadata.create_all(bind=engine)
    with client:  # triggers lifespan
        db = SessionLocal()
        cleanup_db(db)
        
        # Create users
        alice = User(username=ALICE_USERNAME, hashed_password=hash_password("pass"))
        bob = User(username=BOB_USERNAME, hashed_password=hash_password("pass"))
        db.add_all([alice, bob])
        db.flush()
        w1 = Wallet(user_id=alice.id, balance=INITIAL_BALANCE)
        w2 = Wallet(user_id=bob.id, balance=INITIAL_BALANCE)
        db.add_all([w1, w2])
        db.commit()
        db.close()
        
        yield
        
        # db = SessionLocal()
        # cleanup_db(db)
        # db.close()

def get_auth_headers(username: str):
    res = client.post("/auth/login", json={"username": username, "password": "pass"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_escrow_hold_then_release():
    alice_headers = get_auth_headers(ALICE_USERNAME)
    
    # 1. Alice holds 2000 for Bob
    hold_res = client.post(
        "/escrow/payments",
        json={"seller_username": BOB_USERNAME, "amount_bdt": 2000.00},
        headers={**alice_headers, "Idempotency-Key": "test_hold_1"}
    )
    assert hold_res.status_code == 200
    escrow_id = hold_res.json()["id"]
    
    # 2. Check balances after hold
    alice_bal = client.get("/wallets/me", headers=alice_headers).json()["balance_bdt"]
    assert float(alice_bal) == 98000.00
    bob_headers = get_auth_headers(BOB_USERNAME)
    bob_bal = client.get("/wallets/me", headers=bob_headers).json()["balance_bdt"]
    assert float(bob_bal) == 100000.00
    
    # 3. Bob tries to release (should fail - 403)
    bad_release = client.post(f"/escrow/payments/{escrow_id}/release", headers=bob_headers)
    assert bad_release.status_code == 403
    
    # 4. Alice releases
    rel_res = client.post(f"/escrow/payments/{escrow_id}/release", headers=alice_headers)
    assert rel_res.status_code == 200
    
    # 5. Check balances after release
    alice_bal = client.get("/wallets/me", headers=alice_headers).json()["balance_bdt"]
    bob_bal = client.get("/wallets/me", headers=bob_headers).json()["balance_bdt"]
    assert float(alice_bal) == 98000.00
    assert float(bob_bal) == 102000.00
    
    # 6. Second release attempt (should fail - 409)
    rel_res_2 = client.post(f"/escrow/payments/{escrow_id}/release", headers=alice_headers)
    assert rel_res_2.status_code == 409


def test_escrow_hold_then_cancel():
    alice_headers = get_auth_headers(ALICE_USERNAME)
    
    # 1. Alice holds 2000 for Bob
    hold_res = client.post(
        "/escrow/payments",
        json={"seller_username": BOB_USERNAME, "amount_bdt": 2000.00},
        headers={**alice_headers, "Idempotency-Key": "test_hold_2"}
    )
    escrow_id = hold_res.json()["id"]
    
    # 2. Alice cancels
    cancel_res = client.post(f"/escrow/payments/{escrow_id}/cancel", headers=alice_headers)
    assert cancel_res.status_code == 200
    
    # 3. Check balances (Alice should be back to 100000)
    alice_bal = client.get("/wallets/me", headers=alice_headers).json()["balance_bdt"]
    assert float(alice_bal) == 100000.00


def test_escrow_concurrent_release():
    """
    10 threads release the same escrow concurrently -> exactly one 200,
    nine 409, seller credited exactly once.
    """
    alice_headers = get_auth_headers(ALICE_USERNAME)
    hold_res = client.post(
        "/escrow/payments",
        json={"seller_username": BOB_USERNAME, "amount_bdt": 5000.00},
        headers={**alice_headers, "Idempotency-Key": "test_hold_concurrent"}
    )
    escrow_id = hold_res.json()["id"]
    
    def do_release():
        return client.post(f"/escrow/payments/{escrow_id}/release", headers=alice_headers)
    
    success_count = 0
    conflict_count = 0
    
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(do_release) for _ in range(10)]
        for f in as_completed(futures):
            res = f.result()
            if res.status_code == 200:
                success_count += 1
            elif res.status_code == 409:
                conflict_count += 1
                
    assert success_count == 1
    assert conflict_count == 9
    
    # Verify Bob got exactly 5000
    bob_headers = get_auth_headers(BOB_USERNAME)
    bob_bal = client.get("/wallets/me", headers=bob_headers).json()["balance_bdt"]
    assert float(bob_bal) == 105000.00
