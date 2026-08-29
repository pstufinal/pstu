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
