# Scaling Strategy: 10 Million Users

This document outlines our precise scaling plan for the Money Movement API, ensuring ACID compliance and correctness at every step. 

### Phase 0 (Today): Monolith + Row Locks + Pooling
We operate a single PostgreSQL primary instance.
- **Why:** Maximum ACID guarantees with zero distributed systems overhead.
- **Optimizations built today:** `SELECT ... FOR UPDATE` with ascending ID lock order, Connection Pooling, and Database Indexes.
- **Throughput:** A 4-core PostgreSQL instance handles thousands of TPS easily in this phase.

### Phase 1: Read Replicas
When read latency > 100ms or connection utilization exceeds 50%.
- **Action:** Deploy PgBouncer in front of the primary. Stand up asynchronous read replicas.
- **Code Change:** We have already configured `READ_DATABASE_URL` and `get_read_db()` in `app/database.py`. All `GET` requests (e.g., transaction history, wallet balance) will route to replicas automatically.

### Phase 2: Shard Wallets/Ledger by User ID + Monthly Partitions
When we approach 1M users and the primary database's active working set exceeds RAM.
- **Action:** Shard the `wallets`, `transactions`, and `ledger_entries` tables based on a hash of `user_id`.
- **Action:** Implement table partitioning by month for `ledger_entries` to keep active indexes small.
- **Trade-off:** Cross-shard transfers will require 2-Phase Commit (2PC) or Saga patterns, increasing complexity.

### Phase 3: Async Queue for Notifications ONLY
When throughput demands exceed 5M - 10M users.
- **Action:** Offload non-critical workloads (push notifications, email receipts, analytics syncing) to an asynchronous message broker (Kafka/RabbitMQ).
- **Core Principle:** Money movement remains strictly synchronous and ACID compliant. Only side-effects are queued.

***

*Phases 2-3 were not built today because a correct monolith beats a broken distributed system.*
