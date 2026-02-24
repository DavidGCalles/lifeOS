# ADR-012: Unified Memory Core, Domain Segregation & Multi-Tenant Isolation (RBAC)

**Status:** Accepted

**Date:** 2026-02-22 

**Deciders:** DavidGCalles

**Technical Story:** Evolving the dual memory architecture (Firestore + Qdrant) to support true multi-tenant Resource-Based Access Control (RBAC) and unified semantic boundaries.

---

## Context and Problem Statement

LifeOS is transitioning into a multi-user governance system supporting diverse roles: The Sovereign (ADMIN), The Circle (FAMILY), and GUESTS.

Previously, our memory architecture was fundamentally fragmented. We operated a "Dual Engine" where short-term working memory (`SessionManager` via Firestore) and long-term semantic memory (`VectorMemoryManager` via Qdrant) had entirely disparate data schemas, access patterns, and security postures. 

This fragmentation created two critical failure vectors:
1. **The RBAC Vulnerability:** Without a shared access control schema, enforcing strict multi-tenant data boundaries was impossible. Data leaked across roles depending on which "engine" was queried.
2. **Semantic Pollution (The Catch‑all Anti‑pattern):** In the vector store, storing casual conversational snippets alongside dense legal contracts diluted retrieval accuracy. A single embedding model and index configuration cannot optimally serve all data types.

We need a truly unified architecture that guarantees multi‑tenant data sovereignty across *both* memory engines while logically separating different types of knowledge into dedicated semantic spaces.

---

## Decision Drivers

- **Uniform Security Surface (Strict RBAC):** No query may bypass ownership filters, regardless of whether the data lives in the active session (Firestore) or the deep archive (Qdrant).
- **Semantic Purity:** Conversational memory, document knowledge, and system protocols must reside in separate vector spaces for high‑precision retrieval and domain‑specific tuning.
- **Schema Rigidity & Inheritance:** All data ingested by the system MUST share a base schema for access control.
- **Agent Abstraction:** Agents should not care *where* data lives. They must query a single gateway that federates the search securely.

---

## Considered Options

### Option 1: Multi‑Collection / Multi-Database by User (User‑Centric)
Create `memory_admin`, `memory_family` in Qdrant, and separate collections in Firestore per user.
- **Critique:** High overhead. Shared/global queries require federating across an unmaintainable number of collections.

### Option 2: Pure Vectorization (Deprecate SessionManager)
Drop Firestore entirely and write every single conversational turn directly to Qdrant.
- **Critique:** Unacceptable latency for real-time chat operations and excessive embedding costs for ephemeral "noise".

### Option 3: The Unified Gateway with Universal RBAC Schema
Maintain the Dual Engine (Firestore for speed/sessions, Qdrant for semantic depth) but force both to inherit a single `BaseMemoryMetadata` schema, accessed via a centralized `MemoryGateway`.
- **Critique:** Adds routing complexity, but preserves semantic boundaries, real-time speed, and absolute security.

---

## Decision Outcome

**Chosen option:** Option 3 — The Unified Gateway with Universal RBAC Schema.

We will enforce a single, unified data contract across the entire system. Both `SessionManager` and `VectorMemoryManager` become subordinate storage drivers to a unified API that enforces multi‑tenant isolation and domain segregation.

---

## Technical Implementation

### 1. The Universal RBAC Base Schema

Define a Pydantic base model (`BaseMemoryMetadata`) that ALL memory schemas inherit, regardless of the underlying database. It includes:

- `owner_id` (str): Telegram ID of the user/system that generated the memory.
- `visibility` (Enum):
  - `PRIVATE`: retrievable only if `query_user_id == owner_id`.
  - `FAMILY`: retrievable if `query_user_id == owner_id` **or** `query_user_role` is FAMILY/ADMIN.
  - `PUBLIC`: retrievable by anyone.

### 2. Semantic Domain Segregation (Qdrant)

Initialize dedicated Qdrant collections based on data nature, allowing different index parameters per domain:
- `mem_episodic`: Archived conversational snippets, daily logs, agent reflections.
- `mem_documents`: Ingested static files, Drive folders, dense text chunks.
- `mem_system`: Governance rules, protocols, core definitions.

### 3. Session Typing (Firestore)

The `SessionManager` is refactored. The `messages` subcollection in Firestore will no longer accept arbitrary dictionaries. Every document written must comply with a schema that inherits `BaseMemoryMetadata`, defaulting chat turns to `PRIVATE` unless explicitly marked otherwise (e.g., in a shared FAMILY group).

### 4. The Routing Gatekeeper (`MemoryGateway`)

Agents will no longer call `SessionManager` or `VectorMemoryManager` directly. They interact with `MemoryGateway`.

- **Security Injection:** Every `search` or `retrieve_context` operation requires a `UserContext` object. The Gateway injects the `must`/`should` filters (for Qdrant) or `where` clauses (for Firestore) based on `UserContext.telegram_id` and `UserContext.role`. Agents mathematically cannot retrieve data they don't own.
- **Federated Retrieval:** When an agent asks for "recent context about X", the Gateway concurrently queries Firestore (recent explicit turns) and Qdrant (deep semantic matches), merging and deduplicating the results before returning them.

---

## Consequences

### Positive

- ✅ **Zero‑Trust RAG:** Visibility pruning is handled transparently and universally by the gateway layer. Security is guaranteed by design, not by agent prompt adherence.
- ✅ **High‑Precision Context:** Document queries hit only `mem_documents`, eliminating noise from chat memory, while maintaining fast chat history via Firestore.
- ✅ **Clean Abstraction:** Agents have a single point of interaction for all memory operations.

### Negative

- ⚠️ **Federation Latency:** Concurrently querying Firestore and Qdrant and merging results adds overhead to the Fast Track routing.
- ⚠️ **Breaking Change (Total Wipe):** Both the existing Qdrant databases and the Firestore `sessions` collections become obsolete due to the missing RBAC metadata fields. A full database wipe and schema redeployment are required.

# ADR-012: Post-Implementation Review (2026-02-24)

## Status: Validated & Refined

The unified memory architecture and the `MemoryGateway` logic defined in [ADR-012] have been successfully implemented and merged into the core. This review confirms the stability of the multi-tenant isolation and the domain segregation strategy.

### 1. Architectural Integrity
- **Single Point of Truth:** The `MemoryGateway` has successfully replaced direct calls to `SessionManager` and `VectorMemoryManager`. The system now enforces a "Zero-Trust" policy where no memory retrieval is possible without a valid `UserContext`.
- **RBAC Enforcement:** Mathematical filters (Qdrant `should` clauses and Firestore `where` constraints) are correctly injected at the gateway level, ensuring data sovereignty between ADMIN, FAMILY, and GUEST roles.
- **Predictability:** The transition was completed without regression bugs in the routing or agent logic, confirming that the decoupled architecture is now mature and stable.

### 2. Performance Analysis & Profiling
Post-implementation telemetry revealed significant latency spikes (>5s) even within the *Fast Track* lane. To diagnose this, we implemented strict instrumentation across the lifecycle:

- **Gateway Performance:** Profiling logs confirm that `MemoryGateway` operations (Firestore reads/writes and Qdrant semantic searches) are **not** the bottleneck. Execution times for these components remain within acceptable sub-second parameters.
- **Latency Origin:** The friction points have been isolated to the **LLM Orchestration layer** (LiteLLM initialization overhead and model response times) rather than the persistence layer.
- **Action Taken:** Enhanced logging with micro-second precision has been established as a standard for all future modules to monitor execution drift.

### 3. Unified Schema Validation
- **Metadata Inheritance:** The `BaseMemoryMetadata` contract is now strictly enforced via Pydantic. Any attempt to write "legacy" unstructured data now triggers a validation error at the edge, preventing database pollution.
- **Wipe Status:** As anticipated, a full purge of legacy session documents was required to accommodate the new mandatory RBAC fields.