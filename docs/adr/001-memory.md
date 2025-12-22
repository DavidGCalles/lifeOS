# [MADR] 001: Memory Architecture Strategy (Service-Based RAG)
**Status:** Accepted

**Date:** 2025-12-21

**Deciders:** David G. Calles

**Technical Story:** [Issue #16](https://github.com/DavidGCalles/lifeOS/issues/16)

---

## Context and Problem Statement

LifeOS suffers from "catastrophic amnesia" when restarting sessions or containers. The agents lack long-term context about the user and their preferences. We need a system to store and retrieve information ("Memories") semantically and persistently. Furthermore, a future migration to a cloud infrastructure (Serverless or Ephemeral Containers) is anticipated, so solutions based on monolithic local file systems pose a risk of technical debt (deployment lock-in).

---

## Decision Drivers
-   **Cloud-Native:** The architecture must decouple computation (Agents/LifeOS) from storage (Memory) to allow deployments in ephemeral containers (e.g., Cloud Run, Kubernetes).
-   **Portability:** Ability to move data from local to cloud environments without refactoring the application code.

-   **Privacy:** Preference for self-hosted solutions over mandatory SaaS where data leaves our perimeter.
-   **Cost:** Efficiency in the use of embedding models to avoid high recurring costs for read/write operations.

---

## Considered Options

### Option 1: Embedded ChromaDB (Library)

The database runs within the Python process and saves data to a local folder (`./data`).

-   **Risk:** Incompatible with horizontal scaling or serverless environments without complex persistent volumes.

### Option 2: SaaS Vector DB (e.g., Pinecone, Weaveate Cloud)
- **Risk:** Recurring costs, network latency in local development, and loss of data sovereignty.

### Option 3: Dockerized ChromaDB (Client/Server Pattern)

Run the database as an independent microservice in its own container, communicating via an HTTP API.

---

## Decision Outcome
**Chosen option:** **Option 3: Dockerized ChromaDB**.

This option provides a true microservices architecture from day one, facilitating the transition to the cloud without sacrificing privacy or the zero cost of local development.

---

## Technical Implementation

### Architecture

-   A `chromadb` service will be added to the `docker-compose.yml` file (using the official `chromadb/chroma` image).
-   The LifeOS application will be configured to use `ChromaDBClient` in HTTP mode, pointing to the service host instead of direct local persistence.

### Storage

-   **Local:** A Docker volume mapped to the local disk.
-   **Cloud:** A persistent volume or a managed instance, configurable only through environment variables (`CHROMA_HOST`).

### Embeddings

-   The `Google Gemini Embeddings (text-embedding-004)` model will be used, routed through LiteLLM. This ensures high multilingual performance at a low or zero cost.

---

## Consequences

### Positive

-   **Decoupling:** The agent's code is agnostic to where the data resides.
-   **Scalability:** Allows scaling the agents independently of the database.
-   **Privacy:** We keep the data in our own (Container) or controlled infrastructure.

### Negative

-   **Resource Usage:** Slightly increases RAM consumption in the local development environment due to the need to run an additional container for the database.