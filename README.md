# Money Movement API — PSTU Hackathon (Final Round)

A peer-to-peer fake-money transfer service built with **FastAPI + SQLAlchemy 2.x + PostgreSQL**.  
Designed to be **boring and correct** — no microservices, no Redis, no Kafka. Just ACID transactions.

---

## Architecture Overview

```
app/
├── main.py              ← FastAPI entry point, creates tables on startup
├── config.py            ← pydantic-settings, loads .env / env vars
├── database.py          ← SQLAlchemy engine + session factory
├── core/
│   ├── security.py      ← bcrypt hashing, JWT, get_current_user dependency
│   └── money.py         ← Decimal validation (float is banned)
├── models/
│   ├── user.py          ← User table
│   ├── wallet.py        ← Wallet table (NUMERIC 15,2)
│   ├── transaction.py   ← Transaction + LedgerEntry + IdempotencyRecord
│   └── money_request.py ← MoneyRequest (pending/approved/rejected)
├── schemas/             ← Pydantic v2 request/response models
├── services/
│   ├── wallet_service.py    ← create wallet, get balance
│   ├── transfer_service.py  ← THE critical path: atomic transfer
│   └── request_service.py   ← money request CRUD, reuses transfer_service
└── api/
    ├── routes_auth.py       ← POST /auth/register, /auth/login
    ├── routes_transfers.py  ← POST /transfers/send, GET /wallets/me, /transactions/history
    └── routes_requests.py   ← POST /money-requests, /{id}/approve, /{id}/reject
tests/
└── test_race_condition.py   ← 20-thread concurrent transfer stress test
```

**Why a monolith?** For a 6-hour hackathon with a two-person team, a single deployable unit is the right call. Every inter-service call we don't make is a race condition, a timeout, and a retry policy we don't have to debug.

---

## Concurrency & Race Condition Strategy

The system's correctness under concurrency rests on **three PostgreSQL mechanisms**:

### 1. `SELECT … FOR UPDATE` (pessimistic row locking)
Every transfer locks both the sender and recipient wallet rows before reading balances. No other transaction can read-then-write those rows until we commit.

### 2. Global lock ordering (deadlock prevention)
We **always lock wallets in ascending `wallet.id` order**. If Alice (wallet 1) sends to Bob (wallet 2), we lock 1 then 2. If Bob sends to Alice at the same time, his transaction also locks 1 then 2. Two transactions that acquire the same locks in the same order **cannot deadlock** — this is a well-known technique from database textbooks.

### 3. Single atomic transaction
Balance checks, balance updates, Transaction insert, LedgerEntry inserts, and IdempotencyRecord insert all happen in **one PostgreSQL transaction**. Either everything commits or nothing does. There is no window where money disappears or appears.

**Proof:** Run `pytest tests/test_race_condition.py -v`. It fires 20 simultaneous threads (10 alice→bob, 10 bob→alice, 100 BDT each) and asserts exact final balances + total money conservation.

---

## Idempotency

Every `/transfers/send` request **must** include an `Idempotency-Key` header (typically a UUID).

1. **Fast path:** Before acquiring any locks, we check `idempotency_records` for the key. If found, we return the cached response immediately — zero cost.
2. **DB safety net:** The `transactions.idempotency_key` column has a `UNIQUE` constraint. Even if two concurrent requests with the same key both pass the fast-path check, only one `INSERT` will succeed; the other gets an `IntegrityError`, rolls back, and returns the winner's cached response.
3. **Result:** Same key, same response, always. The sender's balance is never charged twice.

---

## Double-Entry Ledger

Every transfer writes **three rows**:

| Table | Row | Example |
|-------|-----|---------|
| `transactions` | 1 row | alice → bob, 2500 BDT |
| `ledger_entries` | DEBIT | wallet=alice, amount=2500, balance_after=97500 |
| `ledger_entries` | CREDIT | wallet=bob, amount=2500, balance_after=102500 |

**Invariant:** `SUM(all DEBIT amounts)` must equal `SUM(all CREDIT amounts)` at all times. If they disagree, we know data is corrupt — something single-entry bookkeeping cannot detect.

`balance_after` on each entry enables point-in-time auditing without replaying the entire ledger.

---

## Scaling to 10M Users in 3 Years

For a 6-hour build, we chose a **single PostgreSQL monolith on purpose** — it gives us ACID guarantees with zero operational overhead. Here is our exact 4-phase scaling plan:

*   **Phase 0 (today):** monolith + row locks + pooling.
*   **Phase 1:** read replicas.
*   **Phase 2:** shard wallets/ledger by user_id + monthly partitions.
*   **Phase 3:** async queue for notifications ONLY.

Phases 2-3 were not built today because a correct monolith beats a broken distributed system.

(For full details, see [`docs/SCALING_STRATEGY.md`](docs/SCALING_STRATEGY.md) and check the `/scaling/metrics` endpoint).

---

## How to Run (No Docker)

### Prerequisites
- Python 3.11+
- PostgreSQL running locally (default port 5432)
- `psql` command-line tool

### Steps

```bash
# 1. Create the database
psql -U postgres -c "CREATE DATABASE moneymove;"

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
# Git Bash / Linux / macOS:
source .venv/bin/activate
# PowerShell:
.venv\Scripts\Activate.ps1
# CMD:
.venv\Scripts\activate.bat

# 4. Install dependencies
pip install -r requirements.txt

# 5. (Optional) Create a .env file
cp .env.example .env  # edit DATABASE_URL if your PG credentials differ

# 6. Start the server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Tables are auto-created on first startup via `Base.metadata.create_all()`.

### Running Tests
```bash
pytest tests/test_race_condition.py -v
```

---

## What AI Generated vs What Humans Decided

| Aspect | Decided by Humans | Generated by AI |
|--------|-------------------|-----------------|
| **Architecture** | Monolith, no Docker, no Redis, single PG — humans chose simplicity for a 6-hour hackathon | N/A |
| **Concurrency strategy** | SELECT FOR UPDATE + ascending lock order — humans specified the technique | AI implemented the locking code and wrote the race-condition test |
| **Double-entry ledger** | Humans decided every transfer must produce DEBIT + CREDIT entries | AI generated the model definitions and service code |
| **Idempotency** | Humans required Idempotency-Key header with unique constraint | AI implemented the fast-path check + IntegrityError fallback |
| **Stack** | Humans chose FastAPI + SQLAlchemy 2.x sync + PostgreSQL + Pydantic v2 + JWT | AI scaffolded all files following the chosen stack |
| **All source code** | Humans reviewed every file, understood every line, and can explain every design decision | AI wrote the initial implementation following the human-specified constraints |
| **Scaling roadmap** | Humans designed the 3-year scaling strategy | AI formatted it into the README |

**Key principle:** AI is the typist, humans are the architects. Every line of code can be explained by the team because the team specified every constraint.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register user, auto-fund wallet with 100,000 BDT |
| POST | `/auth/login` | Login, get JWT |
| GET | `/wallets/me` | Current balance |
| POST | `/transfers/send` | Send money (requires `Idempotency-Key` header) |
| POST | `/money-requests` | Request money from another user |
| POST | `/money-requests/{id}/approve` | Payer approves the request |
| POST | `/money-requests/{id}/reject` | Payer rejects the request |
| GET | `/transactions/history` | Ledger entries for current user |
| GET | `/health` | Liveness probe |
