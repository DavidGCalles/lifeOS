# ADR-007: Standardization on Qdrant and Removal of Multi-Engine Support

* **Status:** Accepted
* **Date:** 2026-01-09
* **Deciders:** DavidGCalles

## Context and Problem Statement

We are transitioning our Vector Search infrastructure to **Qdrant**. Currently, parts of the codebase or proof-of-concept implementations rely on **ChromaDB**.

A proposal was made to implement a `VectorMemoryFactory` pattern to support dual execution: using ChromaDB (in-memory) for local development and Qdrant for production environments.

We need to decide whether the complexity of maintaining an abstraction layer for two distinct vector engines is justified by the convenience of running without Docker in local environments.

## Decision Drivers

* **Environment Parity:** The behavior of the application in the local development environment must match the production environment as closely as possible to prevent "it works on my machine" defects.
* **Feature Utilization:** We want to leverage Qdrant-specific features (e.g., advanced payload filtering, quantization, distinct metric types) without being held back by the "lowest common denominator" of a generic interface.
* **Code Maintainability:** Minimizing the surface area of the codebase that needs testing and maintenance.
* **Developer Experience:** Simplifying the setup while ensuring reliability.

## Considered Options

1.  **Dual Support Strategy:** Implement a `VectorMemoryFactory` with a generic interface. Use ChromaDB for local dev and Qdrant for prod.
2.  **Qdrant-Only Strategy:** Use Qdrant across all environments (via Docker for local dev) and remove ChromaDB dependencies entirely.

## Decision Outcome

Chosen option: **Option 2: Qdrant-Only Strategy**.

We will remove ChromaDB from the stack completely. We will implement a domain-level interface (e.g., `SemanticMemory`) to decouple business logic from the driver, but we will provide **only one implementation** backed by Qdrant.

**Reasoning:**
The "convenience" of ChromaDB for local development is outweighed by the risks of environment divergence. Qdrant is lightweight enough to run effortlessly in Docker for local development (`docker-compose`), ensuring that developers test against the exact same engine logic, indexing algorithms, and filtering syntax used in production.

Maintaining a Factory for two engines would force us to write "Least Common Multiple" code, preventing us from using Qdrant's advanced features effectively.

### Positive Consequences

* **Dev/Prod Parity:** Eliminates bugs caused by differences in vector search algorithms or API behaviors between Chroma and Qdrant.
* **Reduced Complexity:** Removes the need to write, test, and maintain a `ChromaAdapter`. Less code = fewer bugs.
* **Full Power:** We can optimize queries using specific Qdrant capabilities (like specific HNSW parameters) without worrying if Chroma supports them.
* **Clean Dependency Tree:** Removes the Python/System dependencies required by ChromaDB from our project.

### Negative Consequences

* **Docker Requirement:** Developers must have Docker installed and running to execute the application locally (standard practice in modern engineering, but a hard requirement nonetheless).
* **Migration Effort:** Any existing data or logic specific to Chroma in the current codebase must be refactored or discarded.