"""
Race-condition integration test.

Proves that SELECT … FOR UPDATE with ascending wallet-ID lock order prevents:
  1. Lost updates (balance goes wrong)
  2. Negative balances
  3. Money creation / destruction (conservation violated)

Requires a running PostgreSQL with the DATABASE_URL from .env / env var.
Run with:  pytest tests/test_race_condition.py -v
"""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

import pytest

from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models.transaction import IdempotencyRecord, LedgerEntry, Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.transfer_service import execute_transfer

# ── Test-specific constants ───────────────────────────────────────────────────
ALICE_USERNAME = "race_test_alice"
BOB_USERNAME = "race_test_bob"
INITIAL_BALANCE = Decimal("100000.00")
TRANSFER_AMOUNT = Decimal("100.00")
THREADS_PER_DIRECTION = 10  # 10 alice→bob + 10 bob→alice = 20 total


@pytest.fixture(autouse=True)
def _ensure_tables():
    """Make sure all tables exist before the test runs."""
    Base.metadata.create_all(bind=engine)
    yield


def _create_user_with_wallet(
    db, username: str, balance: Decimal = INITIAL_BALANCE
) -> int:
    """Helper: insert a user + funded wallet, return user.id."""
    user = User(username=username, hashed_password=hash_password("testpass"))
    db.add(user)
    db.flush()
    wallet = Wallet(user_id=user.id, balance=balance)
    db.add(wallet)
    db.flush()
    return user.id


# ── THE race-condition test ──────────────────────────────────────────────────

def test_concurrent_transfers_conserve_money():
    """
    Fire 20 threads simultaneously: 10 send alice→bob (100 BDT) and 10 send
    bob→alice (100 BDT). Net movement is zero.

    Assertions:
      • All 20 transfers succeed (no deadlocks, no serialisation failures).
      • Final balances equal starting balances (net zero).
      • Neither balance ever went negative.
      • Total money in the system is exactly conserved.
    """
    # ── Setup: fresh users that don't collide with manual curl tests ──────────
    setup_db = SessionLocal()
    try:
        # Clean up from previous test runs
        users_to_delete = setup_db.query(User).filter(User.username.in_([ALICE_USERNAME, BOB_USERNAME])).all()
        user_ids = [u.id for u in users_to_delete]
        if user_ids:
            wallets = setup_db.query(Wallet).filter(Wallet.user_id.in_(user_ids)).all()
            wallet_ids = [w.id for w in wallets]
            if wallet_ids:
                setup_db.query(LedgerEntry).filter(LedgerEntry.wallet_id.in_(wallet_ids)).delete(synchronize_session=False)
                setup_db.query(Transaction).filter(
                    (Transaction.sender_wallet_id.in_(wallet_ids)) | 
                    (Transaction.recipient_wallet_id.in_(wallet_ids))
                ).delete(synchronize_session=False)
                setup_db.query(Wallet).filter(Wallet.id.in_(wallet_ids)).delete(synchronize_session=False)
            setup_db.query(IdempotencyRecord).filter(IdempotencyRecord.user_id.in_(user_ids)).delete(synchronize_session=False)
            setup_db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        setup_db.commit()

        alice_id = _create_user_with_wallet(setup_db, ALICE_USERNAME)
        bob_id = _create_user_with_wallet(setup_db, BOB_USERNAME)
        setup_db.commit()
    finally:
        setup_db.close()

    # ── Barrier: ensures all 20 threads start at the same instant ─────────────
    # Why a barrier: without it, threads start sequentially and the test
    # degenerates into serial execution, hiding real race conditions.
    barrier = threading.Barrier(THREADS_PER_DIRECTION * 2, timeout=30)
    errors: list[str] = []

    def do_transfer(sender_id: int, recipient_username: str, idempotency_key: str):
        """Each thread gets its own DB session — this is what real concurrent
        HTTP requests would do (one session per request)."""
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            errors.append("Barrier broken — thread did not start in time.")
            return
        session = SessionLocal()
        try:
            execute_transfer(
                db=session,
                sender_user_id=sender_id,
                recipient_username=recipient_username,
                amount_bdt=TRANSFER_AMOUNT,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            errors.append(f"Transfer failed: {exc}")
        finally:
            session.close()

    # ── Fire all 20 threads ───────────────────────────────────────────────────
    with ThreadPoolExecutor(max_workers=THREADS_PER_DIRECTION * 2) as pool:
        futures = []
        for i in range(THREADS_PER_DIRECTION):
            futures.append(
                pool.submit(
                    do_transfer, alice_id, BOB_USERNAME, f"race-ab-{i}"
                )
            )
            futures.append(
                pool.submit(
                    do_transfer, bob_id, ALICE_USERNAME, f"race-ba-{i}"
                )
            )
        for future in as_completed(futures):
            future.result()  # re-raise any unhandled exceptions

    # ── Assertions ────────────────────────────────────────────────────────────
    assert len(errors) == 0, f"Some transfers failed:\n" + "\n".join(errors)

    verify_db = SessionLocal()
    try:
        alice_wallet = verify_db.query(Wallet).filter_by(user_id=alice_id).first()
        bob_wallet = verify_db.query(Wallet).filter_by(user_id=bob_id).first()

        # Net zero: 10 × 100 each way → balances unchanged.
        assert alice_wallet.balance == INITIAL_BALANCE, (
            f"Alice balance wrong: expected {INITIAL_BALANCE}, got {alice_wallet.balance}"
        )
        assert bob_wallet.balance == INITIAL_BALANCE, (
            f"Bob balance wrong: expected {INITIAL_BALANCE}, got {bob_wallet.balance}"
        )

        # No negative balance.
        assert alice_wallet.balance >= Decimal("0"), "Alice balance went negative!"
        assert bob_wallet.balance >= Decimal("0"), "Bob balance went negative!"

        # Conservation of money.
        total_money = alice_wallet.balance + bob_wallet.balance
        expected_total = INITIAL_BALANCE * 2
        assert total_money == expected_total, (
            f"Money not conserved: expected {expected_total}, got {total_money}"
        )
    finally:
        verify_db.close()
