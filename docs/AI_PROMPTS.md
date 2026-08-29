# AI PROMPTS & ENGINEERING DECISION LOG
PSTU IT Carnival 2026 — Final Round — Money Movement Application
This file is a graded deliverable. It logs every AI prompt used, what the AI
generated, and what humans decided. Rule we followed: **rules choose, AI
generates, humans defend.**

---

## ENTRY 1 — Master planning prompt (Hour 0)
Purpose: turn the problem statement into a judge-safe architecture, kill brainrot.

```text
You are a Bangladesh hackathon architecture engine for under-12-hour rounds.
No creativity, no motivation, no overengineering. Given: problem statement,
time limit, team skills, deliverables, judging criteria, region=Bangladesh.
Output exactly: 1. PROBLEM TYPE (classify: crud_business_logic /
fintech_ledger / ai_api_copilot / devops / realtime / system_design).
2. JUDGE WILL TEST (endpoints, schema, concurrency, README, demo flow).
3. HARD CONSTRAINTS (no secrets, no auth unless required, no GPU, synthetic
data, Bangla context). 4. RECOMMENDED STACK (one primary + one backup;
default: FastAPI > PostgreSQL > Docker-less local run > static frontend only
if UI needed). 5. ARCHITECTURE (text diagram, 1 line per component).
6. MINIMUM WINNING SCOPE (MUST / SHOULD / SKIP). 7. FILE STRUCTURE.
8. BUILD ORDER hour-by-hour. 9. TEST CASES (happy path, malformed, negative
amounts, self-send, ghost user, concurrency, persistence). 10. ANTI-BRAINROT
RULES (no UI before API, no microservices, no Redis/Kafka, no auth beyond
JWT, no refactor mid-build, no stack arguments >10 min). 11. FINAL DECISION
(use this stack / build this first / ignore everything else / proof).
BD context: fintech never asks PIN/OTP, never promises refunds; correctness
beats UI; boring stack beats trendy stack; judges read code and variable
names; scaling story to 10M users in 3 years required.
```
AI generated: classification (fintech ledger + concurrency test), stack
verdict, 6-hour build order. Humans decided: final stack, scope freeze.

## ENTRY 2 — Hour-1 backend skeleton prompt (no Docker)
Purpose: build the proven core in one shot, human-to-AI tone.

```text
I'm in a 6-hour hackathon (PSTU final). Money Movement app: register auto-
funds 100,000 BDT; send money; request money + approve/reject. Judges:
frontend only 10%, they will read variable names, ask me to explain any
line, ask about race conditions and scaling to 10M users in 3 years.
Build ONLY backend skeleton. No frontend. No Docker - PostgreSQL runs
locally as a service, app runs with uvicorn. No Redis/Kafka/Celery/
microservices/admin/notifications. Stack: Python + FastAPI + SQLAlchemy 2.x
sync + PostgreSQL + Pydantic v2 + JWT. Structure: app/{models,schemas,
services,api,core}, tests/, requirements.txt, .env.example, README.md,
docs/AI_PROMPTS.md, TEST_COMMANDS.md. Models: User, Wallet NUMERIC(15,2),
Transaction, LedgerEntry DEBIT/CREDIT, MoneyRequest, IdempotencyRecord.
Endpoints: /auth/register, /auth/login, /wallets/me, /transfers/send
(+Idempotency-Key header), /money-requests, /{id}/approve, /{id}/reject,
/transactions/history. Rules with WHY comments: Decimal only; one DB
transaction per transfer; lock wallets SELECT ... FOR UPDATE in ascending
id order; idempotency unique constraint returns original result; double-
entry ledger; register funds 100000.00; clean 4xx JSON, no stack traces.
Names like sender_wallet, amount_bdt, idempotency_key - banned: data/tmp/x.
tests/test_race_condition.py: 20 concurrent threads, exact final balances,
money conserved. README sections incl. "Scaling to 10M users" and "What AI
generated vs humans decided". Finish with full curl test sequence with
expected balances (97500/102500 after 2500; 96300/103700 after 1200
approve; 95300/104700 after 10x100 hammer) and one-line judge defenses.
```
AI generated: full skeleton. Humans decided: local Postgres (no Docker),
lock ordering, schema.

## ENTRY 3 — Scaling Phase-1 prompt
Purpose: judge asked for scalability; implement only Phase 1.

```text
Add Phase-1 scaling readiness. No sharding/Kafka/Redis/microservices.
1. Pooling in database.py: pool_size=20, max_overflow=40, pre_ping,
recycle=3600, timeout=30 + PgBouncer comment. 2. Optional READ_DATABASE_URL
-> replica_engine + get_read_db() wired to GET routes, fallback primary.
3. index=True on 6 FK columns. 4. GET /scaling/metrics: connections vs
max, utilization %, table byte sizes, next_scaling_step quote.
5. docs/SCALING_STRATEGY.md + README section, 4 phases, ending: "Phases 2-3
not built today because a correct monolith beats a broken distributed
system." Names: primary_engine, replica_engine,
connection_utilization_percent. Finish with curl test.
```
AI generated: pooling, replica-ready routing, indexes, metrics endpoint,
docs. Humans decided: Phase 1 only; triggers for later phases.

## ENTRY 4 — Escrow (killer feature) prompt
Purpose: BD f-commerce trust layer.

```text
Add ESCROW reusing the exact atomic pipeline (do not rewrite transfers).
System wallet "ESCROW_HOLD"; table escrow_payments (HELD/RELEASED/
REFUNDED, idempotency_key unique); transactions.type column
TRANSFER|ESCROW_HOLD|ESCROW_RELEASE|ESCROW_REFUND. Endpoints:
/escrow/payments, /{id}/release (buyer only, HELD only), /{id}/cancel,
GET /escrow/payments. release/cancel use FOR UPDATE on escrow row, else
409; seller cannot act (403). Ledger pairs: HOLD debit buyer credit
escrow; RELEASE debit escrow credit seller; REFUND debit escrow credit
buyer. tests/test_escrow.py incl. 10 concurrent releases -> one 200 nine
409. README "Escrow - trust layer for BD f-commerce". Finish with curl
demo + expected balances.
```
AI generated: escrow service + tests. Humans decided: state machine,
buyer-only transitions.

## ENTRY 5 — TrxID + public verify link prompt
```text
Two micro features, do not touch transfer logic. 1. trx_code column unique
"PST26-"+6 chars A-Z2-9, on all transaction types, in responses and
history, startup backfill. WHY: every BD user recognizes a TrxID. 2. GET
/verify/{trx_code} no-auth read-only: type, amount as string, status,
created_at, masked names (3 chars+"***"); 404 clean; nothing else. WHY:
public proof kills fake payment screenshots. Add TEST_COMMANDS lines.
```

## ENTRY 6 — Request hardening + global demo prompt (backend lock)
```text
Final backend work, then freeze. TASK 1: POST /money-requests validates
amount >0 and <= MAX_REQUEST_AMOUNT(100000.00), requester != payer, payer
exists; approve/reject FOR UPDATE, pending-only else 409, payer-only else
403. WHY: negative amounts invert transfer direction; locked transitions
kill double-approve. NO audit endpoint, NO rate limiting. TASK 2:
demo_all.py against live server, unique usernames per run, prints
expected vs actual, exit 1 on fail. Steps: register 3 users 100000; login;
transfer 2500 + trx check; same idempotency key unchanged; bad transfers
(-500, 999999999, self, ghost); request 1200 approve; request security
(-5000, 200000, non-payer 403, concurrent approve one 200 one 409);
escrow hold/release + hold/cancel; escrow 10-thread race; transfer
20-thread race; verify link + 404; DB invariants (debits==credits,
sum wallets == 100000*users, ESCROW_HOLD == HELD sum); final line
"ALL CHECKS PASSED - SYSTEM READY FOR JUDGES".
```
Result: all 13 steps PASSED. Backend frozen after this commit.

## ENTRY 7 — Frontend prompt (teammate, in progress)
```text
Build frontend as static files served by FastAPI. No npm/build/Next.js.
static/: login.html, dashboard.html, send.html, requests.html,
escrow.html. Tailwind CDN + fetch + localStorage JWT. Amounts shown as
returned strings, never parseFloat on money. send.html auto-generates
UUID Idempotency-Key. Dashboard shows balance + history with trx_code.
Requests page approve/reject; escrow page hold/release/cancel. Show ৳;
Bangla digits optional. 4xx shown as clean visible messages. Finish with
click-through demo checklist.
```
(To be filled with result when done.)

## ENTRY 8 — Terminal-only scaling demo prompt
```text
Add a terminal-only scaling demo to my FastAPI money app.
No frontend changes, no backend logic changes, no new dependencies.
The GET /scaling/metrics endpoint already exists - just surface it cleanly.

1. Create demo_scaling.ps1 (PowerShell) and demo_scaling.sh (bash).
   Both call GET http://localhost:8000/scaling/metrics and print one
   clean readable block:
   - active/max connections + utilization percent
   - each table with its size
   - the next_scaling_step line emphasized
   If the server is unreachable, print a clean error and exit 1.

2. TEST_COMMANDS.md: add section "Scaling proof (terminal)" containing:
   .\demo_scaling.ps1        (Windows)
   ./demo_scaling.sh         (bash)
   and the raw one-liner:
   Invoke-RestMethod http://localhost:8000/scaling/metrics | ConvertTo-Json -Depth 5

3. README: one line in the demo section:
   "Scaling is demonstrated from the terminal: .\demo_scaling.ps1"

4. Append this entire prompt to docs/AI_PROMPTS.md as a new logged entry.

Finish by running the script once and showing me its output.
```
Result: Created bash/ps1 scripts fetching from /scaling/metrics.

## ENTRY 9 — OPEN LOG (append every future prompt BEFORE using it)
```text
## ENTRY N — <purpose> | date/time
Prompt: <paste verbatim>
AI generated: ...
Human decisions: ...
```

---

## SCALING — NOW vs LATER (official record)

NOW (implemented, in code):
- Connection pooling 20+40 with pre_ping/recycle/timeout
- Replica-ready read routing (READ_DATABASE_URL, get_read_db)
- FK indexes on all 6 foreign keys
- Live GET /scaling/metrics
- docs/SCALING_STRATEGY.md + README scaling section

LATER (documented only, with trigger points - deliberate non-builds):
- PgBouncer at ~50% connection utilization / ~5K concurrent users
- Read replicas when read latency > 100ms
- Shard wallets/ledger by user_id after 1M users; monthly ledger partitions
- Async queue for notifications ONLY
- Redis token-bucket rate limiting (designed as dependency, not shipped)
Standing defense: "A correct monolith beats a broken distributed system."

## HUMAN vs AI BOUNDARY
AI generated: boilerplate, code drafts, docs, test scaffolds.
Humans decided: stack, schema, lock ordering, idempotency design, escrow
state machine, feature selection, feature rejections (no audit endpoint,
no rate limiting, no fraud guard, no remittance, no Next.js), and the
freeze point.