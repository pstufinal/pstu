# Test Commands

Run these in order after setup. All commands work in **Git Bash on Windows**.

---

## Setup (one time)

```bash
python -m venv .venv
source .venv/bin/activate          # Git Bash / Linux
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Windows CMD:        .venv\Scripts\activate.bat

pip install -r requirements.txt
psql -U postgres -c "CREATE DATABASE moneymove;"
```

---

## Terminal 1: Start the server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Expected:** Server starts, prints "Uvicorn running on http://127.0.0.1:8000". Tables auto-created.

---

## Terminal 2: Run all tests

### Register users (expect 201 with wallet_balance_bdt = "100000.00")

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"pass1234"}'
```
**Expected:** `{"user_id":1,"username":"alice","wallet_balance_bdt":"100000.00","message":"User registered and wallet funded with 100,000.00 BDT."}`

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","password":"pass1234"}'
```
**Expected:** `{"user_id":2,"username":"bob","wallet_balance_bdt":"100000.00","message":"User registered and wallet funded with 100,000.00 BDT."}`

---

### Login (expect JWT in access_token)

```bash
export TOKEN_A=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"pass1234"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

export TOKEN_B=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","password":"pass1234"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```
**Expected:** TOKEN_A and TOKEN_B are set (long JWT strings).

---

### Check balances (expect 100000.00 each)

```bash
curl -s http://localhost:8000/wallets/me -H "Authorization: Bearer $TOKEN_A"
```
**Expected:** `{"username":"alice","balance_bdt":"100000.00"}`

```bash
curl -s http://localhost:8000/wallets/me -H "Authorization: Bearer $TOKEN_B"
```
**Expected:** `{"username":"bob","balance_bdt":"100000.00"}`

---

### Send 2500 BDT (expect success)

```bash
curl -s -X POST http://localhost:8000/transfers/send \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: aaa00000-0000-0000-0000-000000000001" \
  -d '{"recipient_username":"bob","amount_bdt":"2500.00"}'
```
**Expected:** `{"transaction_id":1,"sender":"alice","recipient":"bob","amount_bdt":"2500.00","note":null,"status":"completed"}`

---

### SAME Idempotency-Key again (expect original result, NOT a second charge)

```bash
curl -s -X POST http://localhost:8000/transfers/send \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: aaa00000-0000-0000-0000-000000000001" \
  -d '{"recipient_username":"bob","amount_bdt":"2500.00"}'
```
**Expected:** Same response as above — `transaction_id: 1`, `amount_bdt: "2500.00"`. Balance unchanged.

---

### Check balances after transfer (alice 97500, bob 102500)

```bash
curl -s http://localhost:8000/wallets/me -H "Authorization: Bearer $TOKEN_A"
```
**Expected:** `{"username":"alice","balance_bdt":"97500.00"}`

```bash
curl -s http://localhost:8000/wallets/me -H "Authorization: Bearer $TOKEN_B"
```
**Expected:** `{"username":"bob","balance_bdt":"102500.00"}`

---

### Bob requests 1200 from Alice

```bash
curl -s -X POST http://localhost:8000/money-requests \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json" \
  -d '{"payer_username":"alice","amount_bdt":"1200.00"}'
```
**Expected:** `{"request_id":1,"requester":"bob","payer":"alice","amount_bdt":"1200.00","note":null,"status":"pending"}`

---

### Alice approves the request

```bash
curl -s -X POST http://localhost:8000/money-requests/1/approve \
  -H "Authorization: Bearer $TOKEN_A"
```
**Expected:** `{"request_id":1,"status":"approved","transfer":{...transaction details...}}`

---

### Check balances after approval (alice 96300, bob 103700)

```bash
curl -s http://localhost:8000/wallets/me -H "Authorization: Bearer $TOKEN_A"
```
**Expected:** `{"username":"alice","balance_bdt":"96300.00"}`

```bash
curl -s http://localhost:8000/wallets/me -H "Authorization: Bearer $TOKEN_B"
```
**Expected:** `{"username":"bob","balance_bdt":"103700.00"}`

---

### Error cases (all must return clean 4xx JSON, server stays alive)

```bash
# Negative amount → 422 (Pydantic validation)
curl -s -X POST http://localhost:8000/transfers/send \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: aaa00000-0000-0000-0000-000000000002" \
  -d '{"recipient_username":"bob","amount_bdt":"-500.00"}'
```
**Expected:** 422 with validation error "Amount must be positive."

```bash
# Amount exceeds balance → 400
curl -s -X POST http://localhost:8000/transfers/send \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: aaa00000-0000-0000-0000-000000000003" \
  -d '{"recipient_username":"bob","amount_bdt":"999999999.00"}'
```
**Expected:** 400 with `"Amount exceeds maximum transfer limit."`

```bash
# Send to yourself → 400
curl -s -X POST http://localhost:8000/transfers/send \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: aaa00000-0000-0000-0000-000000000004" \
  -d '{"recipient_username":"alice","amount_bdt":"100.00"}'
```
**Expected:** 400 with `"Cannot send money to yourself."`

```bash
# Non-existent recipient → 404
curl -s -X POST http://localhost:8000/transfers/send \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: aaa00000-0000-0000-0000-000000000005" \
  -d '{"recipient_username":"ghost_user","amount_bdt":"100.00"}'
```
**Expected:** 404 with `"Recipient not found."`

---

### Transaction history (expect DEBIT+CREDIT ledger entries)

```bash
curl -s http://localhost:8000/transactions/history -H "Authorization: Bearer $TOKEN_A"
```
**Expected:** JSON with `entries` array showing DEBIT entries for alice's wallet, consistent with balances.

---

### Race condition test

```bash
pytest tests/test_race_condition.py -v
```
**Expected:** `PASSED` — 20 concurrent transfers complete, exact balances, total money conserved.

---

### Parallel hammer: 10 sends of 100 BDT

```bash
# Git Bash (Linux-style):
seq 1 10 | xargs -P 10 -I {} curl -s -X POST http://localhost:8000/transfers/send \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: hammer-{}" \
  -d '{"recipient_username":"bob","amount_bdt":"100.00"}'

# Windows PowerShell equivalent:
1..10 | ForEach-Object -Parallel {
  Invoke-RestMethod -Method POST -Uri "http://localhost:8000/transfers/send" `
    -Headers @{"Authorization"="Bearer $using:TOKEN_A"; "Content-Type"="application/json"; "Idempotency-Key"="hammer-$_"} `
    -Body '{"recipient_username":"bob","amount_bdt":"100.00"}'
} -ThrottleLimit 10
```

### Check balances after hammer (alice 95300, bob 104700)

```bash
curl -s http://localhost:8000/wallets/me -H "Authorization: Bearer $TOKEN_A"
```
**Expected:** `{"username":"alice","balance_bdt":"95300.00"}`

```bash
curl -s http://localhost:8000/wallets/me -H "Authorization: Bearer $TOKEN_B"
```
**Expected:** `{"username":"bob","balance_bdt":"104700.00"}`
