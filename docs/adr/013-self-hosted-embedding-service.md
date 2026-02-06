# ADR-013- Embedding Service

**Status:** Accepted
**Date:** 2026-02-06
**Context:**
We initially relied on Google's `text-embedding-004` model. On Jan 14th, 2026, Google deprecated this model, causing a critical failure in our vector memory system. Switching to a new proprietary model (e.g., `gemini-embedding-001`) forces a complete wipe of the vector database due to dimension/latent space incompatibility and leaves us vulnerable to future deprecations.

**Decision:**
We will decouple the "Memory Brain" (Embeddings) from the "Reasoning Brain" (LLM).
1.  **Self-Hosted Engine:** We will deploy a dedicated microservice running `michaelfeil/infinity` (a high-performance embedding server).
2.  **Sovereign Model:** We will serve the `intfloat/multilingual-e5-large` model (Open Source, SOTA for multilingual retrieval).
3.  **Immutable Infrastructure:** We control the model version. It will never change unless we explicitly decide to migrate, guaranteeing memory persistence stability.

**Consequences:**
* **Positive:** Complete immunity to external API deprecations. Lower latency (internal network in Docker). Zero cost per token for embeddings.
* **Negative:** Requires deploying and maintaining an extra container/service (Cloud Run). One-time total memory wipe required to migrate to the new vector space (1024 dim).