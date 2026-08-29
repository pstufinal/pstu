import httpx
import uuid
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_full_flow():
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        # 1. Health check
        r = client.get("/health")
        assert r.status_code == 200, f"Health check failed: {r.text}"
        print("1. Health check: OK")

        # 2. Check Static Files
        r = client.get("/")
        assert r.status_code == 200 and "PayPulse" in r.text, "Web UI index.html not served"
        print("2. Static Web UI: OK")

        # 3. Register user alice and bob
        unique = uuid.uuid4().hex[:6]
        alice_name = f"alice_{unique}"
        bob_name = f"bob_{unique}"

        r_alice = client.post("/auth/register", json={"username": alice_name, "password": "password123"})
        assert r_alice.status_code == 201, f"Register Alice failed: {r_alice.text}"
        print(f"3. Register Alice ({alice_name}): Balance = {r_alice.json()['wallet_balance_bdt']} BDT")

        r_bob = client.post("/auth/register", json={"username": bob_name, "password": "password123"})
        assert r_bob.status_code == 201, f"Register Bob failed: {r_bob.text}"
        print(f"4. Register Bob ({bob_name}): Balance = {r_bob.json()['wallet_balance_bdt']} BDT")

        # 4. Login Alice
        r_login_alice = client.post("/auth/login", json={"username": alice_name, "password": "password123"})
        assert r_login_alice.status_code == 200, f"Login Alice failed: {r_login_alice.text}"
        token_alice = r_login_alice.json()["access_token"]

        # 5. Login Bob
        r_login_bob = client.post("/auth/login", json={"username": bob_name, "password": "password123"})
        assert r_login_bob.status_code == 200, f"Login Bob failed: {r_login_bob.text}"
        token_bob = r_login_bob.json()["access_token"]

        # 6. Alice sends 2500.00 BDT to Bob (as requested in problem statement)
        idemp_key = str(uuid.uuid4())
        r_send = client.post(
            "/transfers/send",
            headers={"Authorization": f"Bearer {token_alice}", "Idempotency-Key": idemp_key},
            json={"recipient_username": bob_name, "amount_bdt": "2500.00", "note": "Problem Set Demo: 2500 BDT"}
        )
        assert r_send.status_code == 200, f"Send money failed: {r_send.text}"
        print(f"5. Alice sent 2500 BDT to Bob: OK (TXN #{r_send.json()['transaction_id']})")

        # 7. Check Alice's balance (should be 97500.00)
        r_bal_alice = client.get("/wallets/me", headers={"Authorization": f"Bearer {token_alice}"})
        assert r_bal_alice.json()["balance_bdt"] == "97500.00", f"Alice balance mismatch: {r_bal_alice.text}"
        print("6. Alice balance verified: 97,500.00 BDT")

        # 8. Check Bob's balance (should be 102500.00)
        r_bal_bob = client.get("/wallets/me", headers={"Authorization": f"Bearer {token_bob}"})
        assert r_bal_bob.json()["balance_bdt"] == "102500.00", f"Bob balance mismatch: {r_bal_bob.text}"
        print("7. Bob balance verified: 102,500.00 BDT")

        # 9. Test Idempotency: Re-send with exact same key -> should return cached response, NO extra charge!
        r_retry = client.post(
            "/transfers/send",
            headers={"Authorization": f"Bearer {token_alice}", "Idempotency-Key": idemp_key},
            json={"recipient_username": bob_name, "amount_bdt": "2500.00", "note": "Duplicate retry attempt"}
        )
        assert r_retry.status_code == 200, f"Retry failed: {r_retry.text}"
        r_bal_alice_after = client.get("/wallets/me", headers={"Authorization": f"Bearer {token_alice}"})
        assert r_bal_alice_after.json()["balance_bdt"] == "97500.00", "Idempotency failed! Alice charged twice!"
        print("8. Idempotency test: OK (Same response returned, Alice NOT charged twice)")

        # 10. Bob requests 1200.00 BDT from Alice (Problem Statement: "My friend owes me ৳1,200. I want to collect it")
        r_req = client.post(
            "/money-requests",
            headers={"Authorization": f"Bearer {token_bob}"},
            json={"payer_username": alice_name, "amount_bdt": "1200.00", "note": "Dinner bill share"}
        )
        assert r_req.status_code == 200, f"Money request creation failed: {r_req.text}"
        req_id = r_req.json()["request_id"]
        print(f"9. Bob created money request #{req_id} asking 1200 BDT from Alice: OK")

        # 11. Alice lists requests and sees Bob's request
        r_alice_reqs = client.get("/money-requests", headers={"Authorization": f"Bearer {token_alice}"})
        assert any(r["request_id"] == req_id for r in r_alice_reqs.json()["incoming"]), "Request not visible to Alice"
        print("10. Alice incoming requests query: OK")

        # 12. Alice approves the request (moves 1200 BDT to Bob)
        r_appr = client.post(f"/money-requests/{req_id}/approve", headers={"Authorization": f"Bearer {token_alice}"})
        assert r_appr.status_code == 200, f"Approval failed: {r_appr.text}"
        print("11. Alice approved 1200 BDT request: OK (Transferred atomically)")

        # 13. Verify updated balances
        bal_a = client.get("/wallets/me", headers={"Authorization": f"Bearer {token_alice}"}).json()["balance_bdt"]
        bal_b = client.get("/wallets/me", headers={"Authorization": f"Bearer {token_bob}"}).json()["balance_bdt"]
        assert bal_a == "96300.00", f"Expected Alice balance 96300.00, got {bal_a}"
        assert bal_b == "103700.00", f"Expected Bob balance 103700.00, got {bal_b}"
        print(f"12. Balances after request approval: Alice = {bal_a} BDT, Bob = {bal_b} BDT")

        # 14. Check Double-Entry Ledger History for Alice
        r_hist = client.get("/transactions/history", headers={"Authorization": f"Bearer {token_alice}"})
        entries = r_hist.json()["entries"]
        assert len(entries) >= 2, f"Expected ledger entries, got {len(entries)}"
        print(f"13. Double-entry ledger history for Alice: {len(entries)} entries found")

        # 15. Ledger System Reconciliation
        r_reconcile = client.get("/ledger/reconciliation")
        rec = r_reconcile.json()
        assert rec["is_balanced"] is True, f"Reconciliation failed: {rec}"
        print(f"14. System-wide Double-Entry Reconciliation: 100% BALANCED! (Total Debits: {rec['total_debits_bdt']} == Total Credits: {rec['total_credits_bdt']}, Diff: {rec['difference_bdt']} BDT)")

        print("\n=======================================================")
        print("ALL 14 END-TO-END SYSTEM TESTS PASSED PERFECTLY!")
        print("=======================================================")

if __name__ == "__main__":
    test_full_flow()
