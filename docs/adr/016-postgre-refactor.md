# ADR 016: Relational State Management (PostgreSQL) and Unified Environment Profiles

* Status: Proposed / Accepted
* Deciders: David G. Calles
* Date: 2026-03-25

## Context and Problem Statement

**Architectural Traceability (The ADR-014 Cascade):** The attempt to implement asynchronous background workers outlined in **[ADR-014]** exposed a cascade of systemic blockers. To safely defer heavy cognitive tasks without freezing the real-time Fast Track, the system first required an ultra-fast routing mechanism (**[ADR-015]**). Subsequently, attempting to deploy ADR-014's "Webhook Cron" pattern against our existing NoSQL infrastructure revealed fatal flaws in state management and concurrency control. This ADR (016) and the upcoming ADR (017) are direct resolutions to the infrastructural blockers preventing the safe execution of ADR-014.

Historically, `[lifeOS]` relied on Google Cloud Firestore. As we prepare to expand deferred execution capabilities via the upcoming `TaskManager`, Firestore presents fatal structural limitations:
1. **Concurrency Control:** Document databases cannot safely manage concurrent state machine transitions (e.g., PENDING -> RUNNING -> COMPLETED) without complex optimistic locking. This risks redundant LLM execution across worker instances defined in ADR-014.
2. **Domain & Schema Lock-in:** The NoSQL model couples `session_id`s with external `telegram_id`s, blocking multi-channel expansion. Furthermore, it cannot natively enforce the strict RBAC metadata schema required by ADR-012, pushing fragile validation logic onto Pydantic.

**The Configuration Sprawl:** The impending removal of Firestore forces a refactor of our configuration layer (specifically the `USE_FIRESTORE` flag). Currently, infrastructure toggles (`QDRANT_LOCAL`, `USE_FIRESTORE`, etc.) are managed as disparate variables, risking misconfigured "Frankenstein deployments" (e.g., cloud DB mixed with local vector stores).

## Decision Drivers

* **Worker Concurrency & State:** Need for ACID-compliant transactions and row-level locking (`SELECT ... FOR UPDATE`) to safely orchestrate future background tasks.
* **Data Integrity & Decoupling:** Native schema validation (ENUMs, Foreign Keys, RLS) to enforce ADR-012 at the engine level, and strict separation of external routing identifiers from internal UUIDs.
* **Configuration Sanity:** The deployment infrastructure must be dictated by a single source of truth to guarantee Dev/Prod parity and prevent configuration drift.

## Considered Options

* **Option 1: Firestore + Disparate Feature Flags.** (Rejected: No ACID compliance for state machines, high risk of deployment misconfiguration).
* **Option 2: PostgreSQL (Supabase/Local) + Unified Environment Profiles.** (Chosen).

## Decision Outcome

Chosen option: **Option 2: PostgreSQL + Unified Environment Profiles**.

We will migrate the core `SessionManager` and the foundational tables for the future `TaskManager` to a normalized PostgreSQL schema. The database will act as the single source of truth, utilizing Row Level Security (RLS) to enforce ADR-012 natively.

Simultaneously, we will execute a configuration refactor to implement a **Profile-Driven Architecture** governed by a single master variable: `ENVIRONMENT`.
* **Profile `cloud`:** Injects managed cloud clients (Supabase, Qdrant Cloud).
* **Profile `edge`:** Injects local Docker clients (Local Postgres, Local Qdrant).
* **Profile `hybrid`:** Disables automatic resolution, demanding granular variables.

### Execution Strategy (Strangler Fig Pattern)
A parallel `PostgresSessionManager` will be built to intercept routing and decouple Telegram IDs. Once stable, the `USE_FIRESTORE` flag will be fully deprecated, triggering the configuration layer refactor to rely strictly on the `ENVIRONMENT` profile.

## Consequences

* **Good, because** it physically enforces ADR-012 policies and guarantees ACID compliance for future worker orchestration.
* **Good, because** configuration is vastly simplified. A user only needs to declare `ENVIRONMENT=edge` to spin up a fully cohesive local ecosystem.
* **Bad, because** transitioning query models from NoSQL document streams to SQL pagination requires rewriting the context retrieval logic.

## Next Steps: Closing the ADR-014 Loop (Bridge to ADR-017)
With the relational and transactional foundation established by this ADR, the system is now capable of supporting concurrent task queues safely. The immediate next step is to define **ADR-017**, which will specify the architecture for orchestrating ephemeral workers using this database (resolving the Cloud Tasks vs. PG LISTEN/NOTIFY duality). 

Once ADR-017 is executed, the original vision of **[ADR-014]** (Background Workers & System State Awareness) will be fully unblocked and operational across all deployment profiles.