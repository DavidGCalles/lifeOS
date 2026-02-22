# ADR-012: Unified Memory Core, Domain Segregation & Multi-Tenant Isolation (RBAC)
**Status:** Accepted

**Date:** 2026-02-22 

**Deciders:** DavidGCalles

**Technical Story:** Evolving the memory architecture to support multi-tenant Resource-Based Access Control (RBAC) while preventing semantic pollution.

---

## Context and Problem Statement

LifeOS is transitioning into a multi-user governance system supporting diverse roles: The Sovereign (ADMIN), The Circle (FAMILY), and GUESTS.

Currently, our vector storage (Qdrant) and the `VectorMemoryManager` assume a single global user and a single global collection (`episodic_memory_v1`).
Memory is ingested from multiple sources with vastly different semantic weights:

- Quick synchronous chat interactions.
- Deep, dense document parsing (legal docs, books, logs).
- Core system rules and identity definitions.

Keeping everything in a single collection creates two critical failures:

- **Data Leakage:** Lack of strict data boundaries (RBAC) could expose ADMIN private data to FAMILY agents.
- **Semantic Pollution (The Catch‑all Anti‑pattern):** Storing casual conversational snippets alongside dense legal contracts dilutes retrieval accuracy. A single embedding model and index configuration cannot optimally serve all data types.

We need an architecture that guarantees multi‑tenant data sovereignty while logically separating different types of knowledge into dedicated semantic spaces.

---

## Decision Drivers

- **Strict RBAC Guarantee:** No query may bypass ownership filters across any domain.
- **Semantic Purity:** Conversational memory, document knowledge, and system protocols must reside in separate vector spaces for high‑precision retrieval and domain‑specific tuning.
- **Schema Rigidity & Inheritance:** All data must share a base schema for access control, regardless of domain.
- **Resource Efficiency:** Segregate semantics without an explosion of Qdrant collections.

---

## Considered Options

### Option 1: Multi‑Collection by User (User‑Centric)
Create `memory_admin`, `memory_family`, etc.

- **Critique:** High memory overhead. Shared/ global queries require federating across many collections.

### Option 2: Single Global Collection with RBAC (The Catch‑all)
Store chats, documents, and rules together, filtering solely by metadata.

- **Critique:** Solves RBAC but creates a semantic dumping ground. RAG accuracy suffers when vectors from disparate contexts intermix.

### Option 3: Domain‑Specific Collections with Universal RBAC Schema
Partition collections by knowledge type (e.g., `episodic_chat`, `document_knowledge`, `core_identity`). Enforce one RBAC base schema across all.

- **Critique:** Adds routing complexity but preserves semantic boundaries and security.

---

## Decision Outcome

**Chosen option:** Option 3 — Domain‑Specific Collections with a Universal RBAC Schema.

We will segregate Qdrant into specific logical domains and make the `VectorMemoryManager` enforce multi‑tenant isolation across them.

---

## Technical Implementation

### Semantic Domain Segregation

Initialize dedicated Qdrant collections based on data nature:

- `mem_episodic`: conversational snippets, daily logs, agent observations.
- `mem_documents`: ingested static files, Drive folders, dense text chunks.
- `mem_system`: governance rules, protocols, core definitions.

This permits different embedding models and chunking strategies per domain.

### The Universal RBAC Base Schema

Define a Pydantic base model (`BaseMemoryMetadata`) that all domain schemas inherit. It includes:

- `owner_id` (str): Telegram ID of the user/system that generated the memory.
- `visibility` (Enum):
  - `PRIVATE`: retrievable only if `query_user_id == owner_id`.
  - `FAMILY`: retrievable if `query_user_id == owner_id` **or** `query_user_role` is FAMILY/ADMIN.
  - `PUBLIC`: retrievable by anyone.

Domain‑specific metadata (e.g. `DocumentMetadata`) extends this with fields like `file_name` or `page_number`.

### The Routing Gatekeeper (`VectorMemoryManager`)

Acts as both router and security enforcer:

- **Routing:** `add_memory` and `search_memory` require a `domain` parameter to select the appropriate collection.
- **Security Injection:** `search_memory` also needs a `UserContext` object. Before querying Qdrant, the manager injects `must`/`should` filters based on `UserContext.telegram_id` and `UserContext.role`—agents cannot bypass this.

---

## Consequences

### Positive

- ✅ **High‑Precision RAG:** Document queries hit only `mem_documents`, eliminating noise from chat memory.
- ✅ **Security (Zero‑Trust RAG):** Visibility pruning is handled transparently by the abstraction layer.
- ✅ **Scalability:** Index parameters (e.g., HNSW) can be tuned per domain.

### Negative

- ⚠️ **Implementation Complexity:** Agents and tools must explicitly specify the target domain when accessing memory.
- ⚠️ **Breaking Change:** Existing Qdrant data becomes obsolete; a full database wipe and schema redeployment are required.
