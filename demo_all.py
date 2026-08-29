import json
import re
import sys
import threading
import time
import urllib.request
import urllib.error
import uuid
from decimal import Decimal
from sqlalchemy import create_engine, text  # type: ignore

BASE_URL = "http://localhost:8000"
DB_URL = "postgresql://postgres:postgres@localhost:5432/moneymove"

def print_step(num, desc):
    print(f"\n[{num}/13] {desc}")

def assert_val(expected, actual, msg=""):
    if expected != actual:
        print(f"FAIL: {msg} (Expected: {expected}, Got: {actual})")
        sys.exit(1)

def req(method, path, data=None, token=None, headers=None, expected_status=200):
    url = BASE_URL + path
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if headers:
        h.update(headers)
    
    req_data = json.dumps(data).encode("utf-8") if data else None
    request = urllib.request.Request(url, data=req_data, headers=h, method=method)
    
    try:
        with urllib.request.urlopen(request) as response:
            status = response.getcode()
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8")
    except Exception as e:
        print(f"FAIL: Request {method} {path} failed: {e}")
        sys.exit(1)
        
    if status != expected_status:
        print(f"FAIL: {method} {path} Expected {expected_status}, Got {status}. Body: {body}")
        sys.exit(1)
        
    return json.loads(body) if body else {}

def get_balance(token):
    res = req("GET", "/wallets/me", token=token)
    return Decimal(res["balance_bdt"])

def main():
    print("--- PSTU HACKATHON BACKEND DEMO ---")
    
    # STEP 1
    print_step(1, "Register 3 users -> each wallet exactly 100000.00")
    suffix = int(time.time() * 1000)
    users = [f"demo_{i}_{suffix}" for i in range(1, 4)]
    
    for u in users:
        res = req("POST", "/auth/register", {"username": u, "password": "pass1234"}, expected_status=201)
        assert_val("100000.00", res["wallet_balance_bdt"], f"Initial balance for {u}")
        
    # STEP 2
    print_step(2, "Login all 3 -> tokens work on GET /wallets/me")
    tokens = []
    for u in users:
        res = req("POST", "/auth/login", {"username": u, "password": "pass1234"})
        tokens.append(res["access_token"])
        
    for idx, t in enumerate(tokens):
        bal = get_balance(t)
        assert_val(Decimal("100000.00"), bal, f"Balance check {users[idx]}")
        
    # STEP 3
    print_step(3, "Transfer 2500.00 user1->user2 with Idempotency-Key K1")
    k1 = str(uuid.uuid4())
    res3 = req("POST", "/transfers/send", 
               {"recipient_username": users[1], "amount_bdt": 2500.00}, 
               token=tokens[0], headers={"Idempotency-Key": k1})
    
    trx_code = res3["trx_code"]
    if not re.match(r"^PST26-[A-Z2-9]{6}$", trx_code):
        print(f"FAIL: trx_code format invalid: {trx_code}")
        sys.exit(1)
        
    b1 = get_balance(tokens[0])
    b2 = get_balance(tokens[1])
    assert_val(Decimal("97500.00"), b1, "User1 balance after transfer")
    assert_val(Decimal("102500.00"), b2, "User2 balance after transfer")
    
    # STEP 4
    print_step(4, "Repeat same K1 -> same transaction, balances unchanged")
    res4 = req("POST", "/transfers/send", 
               {"recipient_username": users[1], "amount_bdt": 2500.00}, 
               token=tokens[0], headers={"Idempotency-Key": k1})
    assert_val(trx_code, res4["trx_code"], "Replay should return same trx_code")
    assert_val(Decimal("97500.00"), get_balance(tokens[0]), "User1 unchanged")
    assert_val(Decimal("102500.00"), get_balance(tokens[1]), "User2 unchanged")
    
    # STEP 5
    print_step(5, "Bad transfers: -500, 999999999, self, ghost recipient")
    req("POST", "/transfers/send", {"recipient_username": users[1], "amount_bdt": -500}, tokens[0], {"Idempotency-Key": str(uuid.uuid4())}, 422)
    req("POST", "/transfers/send", {"recipient_username": users[1], "amount_bdt": 999999999}, tokens[0], {"Idempotency-Key": str(uuid.uuid4())}, 400)
    req("POST", "/transfers/send", {"recipient_username": users[0], "amount_bdt": 100}, tokens[0], {"Idempotency-Key": str(uuid.uuid4())}, 400)
    req("POST", "/transfers/send", {"recipient_username": "ghost_123", "amount_bdt": 100}, tokens[0], {"Idempotency-Key": str(uuid.uuid4())}, 404)
    print("Server alive and rejected all bad requests.")
    
    # STEP 6
    print_step(6, "user2 requests 1200.00 from user1; user1 approves")
    res_req = req("POST", "/money-requests", {"payer_username": users[0], "amount_bdt": 1200.00}, token=tokens[1])
    req_id = res_req["request_id"]
    req("POST", f"/money-requests/{req_id}/approve", token=tokens[0])
    assert_val(Decimal("96300.00"), get_balance(tokens[0]), "User1 balance after approve")
    assert_val(Decimal("103700.00"), get_balance(tokens[1]), "User2 balance after approve")
    
    # STEP 7
    print_step(7, "Request security bounds and concurrent approves")
    req("POST", "/money-requests", {"payer_username": users[0], "amount_bdt": -5000}, token=tokens[1], expected_status=422)
    req("POST", "/money-requests", {"payer_username": users[0], "amount_bdt": 200000}, token=tokens[1], expected_status=422)
    
    res_req2 = req("POST", "/money-requests", {"payer_username": users[0], "amount_bdt": 100.00}, token=tokens[1])
    req2_id = res_req2["request_id"]
    # Non-payer approve (User2 tries to approve their own request)
    req("POST", f"/money-requests/{req2_id}/approve", token=tokens[1], expected_status=403)
    
    # Concurrent approve
    results_7 = []
    def do_approve():
        url = BASE_URL + f"/money-requests/{req2_id}/approve"
        request = urllib.request.Request(url, method="POST", headers={"Authorization": f"Bearer {tokens[0]}"})
        try:
            with urllib.request.urlopen(request) as response:
                results_7.append(response.getcode())
        except urllib.error.HTTPError as e:
            results_7.append(e.code)
            
    t1 = threading.Thread(target=do_approve)
    t2 = threading.Thread(target=do_approve)
    t1.start(); t2.start()
    t1.join(); t2.join()
    
    results_7.sort()
    assert_val([200, 409], results_7, "Concurrent approves should yield exactly one 200 and one 409")
    assert_val(Decimal("96200.00"), get_balance(tokens[0]), "User1 balance after concurrent approve")
    
    # STEP 8
    print_step(8, "Escrow: Hold -> Release -> Exact balances. Hold -> Cancel -> Refund")
    esc1 = req("POST", "/escrow/payments", {"seller_username": users[1], "amount_bdt": 2000.00}, tokens[0], {"Idempotency-Key": str(uuid.uuid4())})
    req("POST", f"/escrow/payments/{esc1['id']}/release", token=tokens[0])
    assert_val(Decimal("94200.00"), get_balance(tokens[0]), "User1 after escrow release")
    assert_val(Decimal("105800.00"), get_balance(tokens[1]), "User2 after escrow release")
    
    esc2 = req("POST", "/escrow/payments", {"seller_username": users[1], "amount_bdt": 1000.00}, tokens[0], {"Idempotency-Key": str(uuid.uuid4())})
    req("POST", f"/escrow/payments/{esc2['id']}/cancel", token=tokens[0])
    assert_val(Decimal("94200.00"), get_balance(tokens[0]), "User1 after escrow cancel (refunded)")
    
    # STEP 9
    print_step(9, "Escrow race: 10 concurrent releases")
    esc3 = req("POST", "/escrow/payments", {"seller_username": users[1], "amount_bdt": 500.00}, tokens[0], {"Idempotency-Key": str(uuid.uuid4())})
    esc3_id = esc3["id"]
    
    results_9 = []
    def do_release():
        url = BASE_URL + f"/escrow/payments/{esc3_id}/release"
        request = urllib.request.Request(url, method="POST", headers={"Authorization": f"Bearer {tokens[0]}"})
        try:
            with urllib.request.urlopen(request) as response:
                results_9.append(response.getcode())
        except urllib.error.HTTPError as e:
            results_9.append(e.code)
            
    threads = [threading.Thread(target=do_release) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    success_count = results_9.count(200)
    conflict_count = results_9.count(409)
    assert_val(1, success_count, "Escrow concurrent release 200 count")
    assert_val(9, conflict_count, "Escrow concurrent release 409 count")
    assert_val(Decimal("93700.00"), get_balance(tokens[0]), "User1 after 10-thread escrow")
    assert_val(Decimal("106300.00"), get_balance(tokens[1]), "User2 after 10-thread escrow")
    
    # STEP 10
    print_step(10, "Transfer race: 20 concurrent transfers (10 each direction, 100.00)")
    def transfer(sender_idx, recipient_username, idempotency):
        url = BASE_URL + "/transfers/send"
        data = json.dumps({"recipient_username": recipient_username, "amount_bdt": 100.00}).encode("utf-8")
        headers = {"Authorization": f"Bearer {tokens[sender_idx]}", "Idempotency-Key": idempotency, "Content-Type": "application/json"}
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request):
                pass
        except:
            pass # ignore errors here, we assert on balance

    race_threads = []
    for _ in range(10):
        race_threads.append(threading.Thread(target=transfer, args=(0, users[1], str(uuid.uuid4()))))
        race_threads.append(threading.Thread(target=transfer, args=(1, users[0], str(uuid.uuid4()))))
        
    for t in race_threads: t.start()
    for t in race_threads: t.join()
    
    # 10 * 100 sent by 0 to 1 = 1000
    # 10 * 100 sent by 1 to 0 = 1000
    # Net change should be zero
    assert_val(Decimal("93700.00"), get_balance(tokens[0]), "User1 after 20-thread transfer race")
    assert_val(Decimal("106300.00"), get_balance(tokens[1]), "User2 after 20-thread transfer race")

    # STEP 11
    print_step(11, "Verify link: GET /verify/{trx_code}")
    v_res = req("GET", f"/verify/{trx_code}")
    assert_val("TRANSFER", v_res["type"], "Verify type")
    assert_val("2500.00", v_res["amount"], "Verify amount")
    assert_val(f"{users[0][:3]}***", v_res["sender_masked"], "Masked sender")
    assert_val(f"{users[1][:3]}***", v_res["receiver_masked"], "Masked receiver")
    
    req("GET", "/verify/PST26-FAKEXX", expected_status=404)
    
    # STEP 12
    print_step(12, "Ledger invariants via direct DB connection")
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        debits = conn.execute(text("SELECT SUM(amount_bdt) FROM ledger_entries WHERE entry_type = 'DEBIT'")).scalar()
        credits = conn.execute(text("SELECT SUM(amount_bdt) FROM ledger_entries WHERE entry_type = 'CREDIT'")).scalar()
        assert_val(debits, credits, "Global debits MUST equal global credits")
        
        users_count = conn.execute(text("SELECT COUNT(*) FROM users WHERE username != 'ESCROW_HOLD'")).scalar()
        total_wallet_balance = conn.execute(text("SELECT SUM(balance) FROM wallets")).scalar()
        assert_val(Decimal(str(users_count * 100000.00)), total_wallet_balance, "System money supply invariant")
        
        escrow_hold_sys_id = conn.execute(text("SELECT id FROM users WHERE username = 'ESCROW_HOLD'")).scalar()
        escrow_wallet_bal = conn.execute(text(f"SELECT balance FROM wallets WHERE user_id = {escrow_hold_sys_id}")).scalar()
        total_held = conn.execute(text("SELECT SUM(amount) FROM escrow_payments WHERE status = 'HELD'")).scalar() or Decimal("0.00")
        assert_val(total_held, escrow_wallet_bal, "Escrow wallet balance matches HELD escrow rows")

    # STEP 13
    print_step(13, "Final conclusion")
    print("\n============================================================")
    print(" ALL CHECKS PASSED - SYSTEM READY FOR JUDGES")
    print("============================================================\n")
    sys.exit(0)

if __name__ == "__main__":
    main()
