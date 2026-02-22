# ADR-013: Embedding Service

**Status:** deployed
**Date:** 2026-02-06
**Deciders:** DavidGCalles
**Context:**
We initially relied on Google's `text-embedding-004` model. On Jan 14th, 2026, Google deprecated this model, causing a critical failure in our vector memory system. Switching to a new proprietary model (e.g., `gemini-embedding-001`) forces a complete wipe of the vector database due to dimension/latent space incompatibility and leaves us vulnerable to future deprecations.

**Decision:**
We will decouple the "Memory Brain" (Embeddings) from the "Reasoning Brain" (LLM).
1.  **Self-Hosted Engine:** We will deploy a dedicated microservice running `michaelfeil/infinity` (a high-performance embedding server).
2. **Sovereign Model:** We will serve the `intfloat/multilingual-e5-small` model (Open Source, chosen for its balance of performance and resource usage). While `e5-large` offers higher semantic quality (1024 dimensions), `e5-small` (384 dimensions) provides sufficient performance for our "Fast Track" and retrieval needs with reduced latency and cost. This trade-off is accepted to optimize for operational efficiency.
3. **Immutable Infrastructure:** We control the model version. It will never change unless we explicitly decide to migrate, guaranteeing memory persistence stability.

**Consequences:**
* **Positive:** Complete immunity to external API deprecations. Lower latency (internal network in Docker). Zero cost per token for embeddings.
* **Negative:** Requires deploying and maintaining an extra container/service (Cloud Run). One-time total memory wipe required to migrate to the new vector space (384 dim). This decision accepts a trade-off in raw semantic quality for improved latency and reduced operational cost with the `e5-small` model.