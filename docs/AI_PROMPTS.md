# AI Prompts Log

This file documents all AI prompts used during development, as required by the PSTU Hackathon judging criteria.

---

## Entry #1 — 2026-08-29 (Initial Backend Skeleton)

**Prompt (verbatim):**

> Hey, listen carefully, I'll explain once.
>
> I'm in a 6-hour hackathon (PSTU final round, Bangladesh). The problem is a
> "Money Movement Application": users register and automatically get 100,000 BDT
> fake balance, they can send money to each other, and they can request money
> from someone else and that person can approve or reject the request.
> The judges told us straight: frontend is only 10% of the score, the backend is
> the whole game. They will open our repo, read our variable names, ask me to
> explain any line of code, and specifically ask about race conditions,
> concurrency, and how this scales to 10 million users in 3 years.
>
> So for this first hour I want you to build me ONLY the backend skeleton.
> No frontend. No Docker at all - I don't need it, I have PostgreSQL running
> locally as a normal service, and the app must just run with uvicorn.
> No Redis, no Kafka, no Celery, no microservices, no admin panel,
> no notifications. Boring and correct.
>
> Stack: Python + FastAPI + SQLAlchemy 2.x (sync) + PostgreSQL + Pydantic v2 +
> simple JWT auth. DATABASE_URL comes from an env var with the local default
> postgresql://postgres:postgres@localhost:5432/moneymove
>
> Structure it like this:
>
> app/
>   main.py
>   config.py
>   database.py
>   models/        (user.py, wallet.py, transaction.py, money_request.py)
>   schemas/       (auth.py, transfer.py, money_request.py)
>   services/      (wallet_service.py, transfer_service.py, request_service.py)
>   api/           (routes_auth.py, routes_transfers.py, routes_requests.py)
>   core/          (security.py, money.py)
> tests/
>   test_race_condition.py
> requirements.txt
> .env.example
> README.md
> docs/AI_PROMPTS.md
> TEST_COMMANDS.md
>
> Models: User; Wallet (one per user, balance NUMERIC(15,2)); Transaction;
> LedgerEntry (DEBIT / CREDIT); MoneyRequest (pending/approved/rejected);
> IdempotencyRecord.
>
> Endpoints (exact names):
> POST /auth/register            {username, password} -> creates user + wallet funded with 100000.00
> POST /auth/login               -> JWT
> GET  /wallets/me               -> current balance
> POST /transfers/send           {recipient_username, amount_bdt, note?} + Idempotency-Key header
> POST /money-requests           {payer_username, amount_bdt, note?}
> POST /money-requests/{id}/approve   (only the payer can approve, reuses the transfer service)
> POST /money-requests/{id}/reject
> GET  /transactions/history
>
> Engineering rules - and put a one-line "why" comment on each of these in the
> code, because judges WILL ask me to explain them:
> 1. Money is Decimal everywhere, NUMERIC(15,2) in the DB. Float is banned.
> 2. One transfer = ONE database transaction. Lock both wallet rows with
>    SELECT ... FOR UPDATE, always in ascending wallet id order so we can't deadlock.
> 3. Every send needs an Idempotency-Key with a unique constraint. Same key twice
>    returns the original result, it never charges twice.
> 4. Double-entry ledger: every transfer writes 1 Transaction + 2 LedgerEntry rows.
>    Balances and ledger must always agree.
> 5. Register auto-creates the wallet with 100000.00.
> 6. Bad input returns clean 4xx JSON. Never 500 on bad input, never a stack trace.
>
> Code style: name variables like a real payments codebase - sender_wallet,
> recipient_wallet, amount_bdt, idempotency_key, ledger_entries, request_payer.
> If you write data, tmp, info, obj or x, I will make you rewrite it.
> Keep functions short. Every service function gets a docstring explaining WHY,
> not what.
>
> Two paperwork things that are actually graded:
> - Create docs/AI_PROMPTS.md and paste this entire prompt in it as entry #1 with
>   today's date. The judges said our AI prompts must be in the repo.
> - README.md needs these sections: Architecture Overview; Concurrency & Race
>   Condition Strategy; Idempotency; Double-Entry Ledger; "Scaling to 10M users in
>   3 years" (shard wallets/ledger by user_id, read replicas for history, queue
>   for non-critical events - and state clearly that for a 6-hour build we chose a
>   single Postgres monolith on purpose, for ACID); How to run WITHOUT Docker;
>   "What AI generated vs what humans decided".
>
> Also write tests/test_race_condition.py: create alice and bob, fire 20 threads
> (10 transfers alice->bob and 10 transfers bob->alice, 100 BDT each) at the same
> time, then assert exact final balances, no negative balance ever, and total
> money conserved.
>
> Now the important part. When the code is done, it must pass ALL of the
> following commands, in this exact order, after a successful build. Copy them
> into TEST_COMMANDS.md with the expected result written next to each command.
> I'm on Windows, so I'll run these in Git Bash - if any command is Linux-only,
> add the Windows equivalent next to it. If even one of these would fail with
> the code you wrote, fix the code BEFORE you hand it to me:
>
> [full test commands omitted for brevity — see TEST_COMMANDS.md]
>
> When you hand everything over, finish with a one-line judge-defense for each
> major decision (row locking, idempotency, Decimal, double-entry ledger,
> monolith, no Docker) so I can say them out loud in Q&A without thinking.

**What the AI produced:** The entire backend skeleton (31 files), including all models, services, routes, race-condition test, README, and this prompt log.

**What the humans decided:** Architecture (monolith), stack (FastAPI + SQLAlchemy sync), concurrency strategy (SELECT FOR UPDATE + ascending lock order), all engineering constraints, variable naming conventions, and every design trade-off.

---

## 3. Escrow Feature (Trust Layer)

**Prompt:**
> Add an ESCROW feature to my FastAPI + PostgreSQL money app.
> Context you must respect: we already have users, wallets (NUMERIC(15,2)),
> a double-entry ledger (transactions + ledger_entries), idempotency keys,
> and row locking with SELECT ... FOR UPDATE in ascending wallet id order.
> Escrow must reuse this exact pipeline. Do NOT rewrite existing transfer logic.
> 
> BD reason (put this sentence in README): "Bangladesh f-commerce runs on
> Facebook trust - buyers fear paying for goods that never arrive, sellers
> fear shipping without payment. Escrow makes this app the trust layer."
> 
> Build exactly this:
> 
> 1. System wallet username "ESCROW_HOLD", created at startup if missing.
> 2. Table escrow_payments: id, buyer_user_id FK, seller_user_id FK,
>    amount NUMERIC(15,2), status (HELD / RELEASED / REFUNDED),
>    idempotency_key unique, note, created_at, decided_at.
> 3. transactions table: if a type column does not exist, add it with values
>    TRANSFER | ESCROW_HOLD | ESCROW_RELEASE | ESCROW_REFUND
>    (default TRANSFER, old rows unaffected).
> 
> Endpoints:
> POST /escrow/payments {seller_username, amount_bdt, note?}
>    + Idempotency-Key header -> buyer pays into escrow (status HELD)
> POST /escrow/payments/{id}/release -> buyer only, only from HELD
> POST /escrow/payments/{id}/cancel  -> buyer only, only from HELD (refund)
> GET  /escrow/payments -> list where I am buyer or seller
> 
> State machine rules (one-line WHY comment on each):
> - release/cancel load the escrow row with FOR UPDATE and continue only
>   if status == HELD, otherwise 409
> - seller can NOT release or cancel (403)
> - every money move = ONE DB transaction, wallets locked in ascending id
>   order (only the wallets involved), 2 ledger entries per move:
>   HOLD:    DEBIT buyer,  CREDIT escrow
>   RELEASE: DEBIT escrow, CREDIT seller
>   REFUND:  DEBIT escrow, CREDIT buyer
> - Decimal only, no floats, clean 4xx JSON, no stack traces
> 
> Tests in tests/test_escrow.py, all must pass:
> - hold 2000 then release: buyer 98000, seller 102000 (start 100000 each)
> - hold 2000 then cancel: buyer back to 100000
> - second release attempt -> 409, balances unchanged
> - seller tries release -> 403
> - 10 threads release the same escrow concurrently -> exactly one 200,
>   nine 409, seller credited exactly once
> - the original 20-thread transfer race test must still pass
> 
> Docs:
> - README section "Escrow - trust layer for BD f-commerce"
> - append this whole prompt to docs/AI_PROMPTS.md as a new logged entry
> 
> Finish with the exact curl demo sequence (register alice + bob, hold 2000,
> show balances, release, show balances, then a second escrow that gets
> cancelled) with the expected numbers written next to each command.

---

## Entry 4 — TrxID + public verify link
Date: 2026-08-29 | PSTU Final Round | Hour ~4-5
Purpose: two micro killer-features on top of the proven core, without touching transfer/escrow logic.

### PROMPT (pasted verbatim into the AI tool)

Add two small features to my FastAPI + PostgreSQL money app.
Do NOT change existing transfer/escrow logic except where stated.
After both features, the 20-thread transfer race test and the 10-thread
escrow test must still pass. Decimal only, no new dependencies, no Docker.

FEATURE 1 — bKash-style TrxID:
- add column trx_code to the transactions table, unique, not null
- format: "PST26-" + 6 random chars from A-Z and 2-9 (no 0, 1, O, I)
- generate in Python when creating TRANSFER, ESCROW_HOLD,
  ESCROW_RELEASE, ESCROW_REFUND rows
- if any old rows have null trx_code, backfill them at startup
- return trx_code in: transfer response, escrow responses, and every
  item of GET /transactions/history
- WHY comment: "Every BD user recognizes a TrxID instantly -
  we speak the local money language."

FEATURE 2 — public verify link (anti fake-screenshot fraud):
- GET /verify/{trx_code} - NO auth, read-only
- returns JSON: trx_code, type, amount (string with 2 decimals),
  status, created_at, sender_masked, receiver_masked
- masking rule: first 3 chars of username + "***" (example: "ali***")
- unknown trx_code -> 404 with clean JSON
- return NOTHING else: no balances, no history, no internal ids
- WHY comment: "Public proof-of-payment kills fake payment
  screenshots in BD f-commerce."

Also:
- append 3 curl lines to TEST_COMMANDS.md (verify a transfer,
  verify an escrow release, one 404 case) with expected output
- finish with the exact curl demo sequence for both features and
  the expected JSON of each call

### What the AI generated
- trx_code column + generator + startup backfill
- GET /verify/{trx_code} read-only endpoint
- TEST_COMMANDS.md additions

### Human decisions (NOT AI)
- Chose these two features as the final feature set; backend frozen after this
- Masking rule (3 chars + ***), auth-free read-only design,
  amount returned as string to avoid float JSON issues
- Required both stress tests green before commit

---

## Entry 5 — Final Backend Lockdown & Global Demo Script
Date: 2026-08-29 | PSTU Final Round | Hour ~5-6
Purpose: Security hardening and a comprehensive integration testing script.

### PROMPT (pasted verbatim into the AI tool)

Two tasks, in this order. This is the final backend work; after this the
backend freezes forever. The 20-thread transfer test and the 10-thread
escrow test must still pass at the end.

TASK 1 - REQUEST-MONEY SECURITY HARDENING (only this, nothing else):
- POST /money-requests: amount must be > 0 and <= MAX_REQUEST_AMOUNT
  (config constant 100000.00); requester != payer; payer must exist (404)
- approve and reject: load the request row with SELECT ... FOR UPDATE,
  continue only from status pending otherwise 409; only the payer may
  act otherwise 403
- WHY comment on each guard: "a negative request amount would invert the
  transfer direction; locked status transitions make double-approve
  impossible - user input is never trusted."
- Do NOT add an audit endpoint. Do NOT add rate limiting. Nothing else.

TASK 2 - GLOBAL DEMO SCRIPT covering every feature:
Create demo_all.py at repo root. It must:
- run against the live server at http://localhost:8000 (already running)
- generate unique usernames per run (timestamp suffix) so it can run
  repeatedly without resetting the DB
- print each step: number, what it tests, expected, actual, PASS/FAIL
- exit code 1 if any step fails
Steps in this exact order:
 1  register 3 users -> each wallet exactly 100000.00
 2  login all 3 -> tokens work on GET /wallets/me
 3  transfer 2500.00 user1->user2 with Idempotency-Key K1 ->
    balances 97500.00 / 102500.00; response trx_code matches
    PST26- plus 6 chars from A-Z and 2-9
 4  repeat same K1 -> same transaction, balances unchanged
 5  bad transfers: -500 -> 4xx; 999999999 -> 4xx; send to self -> 4xx;
    ghost recipient -> 404; server still alive after all
 6  user2 requests 1200.00 from user1; user1 approves ->
    96300.00 / 103700.00
 7  request security: request -5000 -> 4xx; request 200000 -> 4xx;
    non-payer approve -> 403; two concurrent approves of one request ->
    exactly one 200 and one 409, money moves exactly once
 8  escrow: user1 holds 2000.00 to user2 -> release -> exact balances;
    second hold -> cancel -> buyer refunded exactly
 9  escrow race: 10 concurrent releases of one held escrow ->
    exactly one 200, nine 409
 10 transfer race: 20 concurrent transfers (10 each direction, 100.00)
    with unique idempotency keys -> exact expected final balances
 11 verify link: GET /verify/{trx_code} from step 3 -> returns type,
    amount "2500.00", masked usernames (3 chars + "***"); fake trx -> 404
 12 ledger invariants via direct DB connection (DATABASE_URL):
    sum(debits) == sum(credits);
    sum(all wallet balances) == 100000.00 * number of users;
    ESCROW_HOLD wallet balance == sum of HELD escrow amounts
 13 final line: "ALL CHECKS PASSED - SYSTEM READY FOR JUDGES"

Rules: Decimal only, exact amount comparisons, no floats, no new
dependencies, short functions with WHY docstrings.

Also:
- TEST_COMMANDS.md: add the line "python demo_all.py"
- README: add a "Full System Demo" section with that one command
- append this entire prompt to docs/AI_PROMPTS.md as a new logged entry

Finish by running demo_all.py yourself and showing me the full output.
