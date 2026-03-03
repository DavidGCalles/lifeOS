# ADR-015: Two-Stage Routing Architecture (Zero-Shot + LLM Fallback)

## Status
Accepted

## Context
Currently, message routing—deciding which specialized agent should process a user prompt—is handled by a general-purpose Large Language Model (LLM) via the `CrewOrchestrator` (as defined in ADR-008). 

While functional, this approach introduces significant architectural friction:
1. **Inefficiency:** Using an autoregressive generative model for a discriminative classification task is a misallocation of computing resources.
2. **High Latency:** The LLM routing adds several seconds (approx. 3-8s) of delay to every interaction, degrading the user experience for quick commands (e.g., adding a grocery item).
3. **Cost/Token Waste:** Standard text classification unnecessarily consumes API quota and tokens.

However, the LLM cannot be entirely replaced. The system must fulfill the **FR-02 (Multimodal)** requirement. Standard zero-shot classifiers are blind and cannot process image payloads. 

## Decision
We will implement a **Two-Stage Router** that combines the speed of lightweight mathematical models with the deep reasoning and visual capabilities of the LLM:

* **Stage 1: Zero-Shot Classification (Infinity Engine)**
  * All strictly text-based inputs will be sent to the `/classify` endpoint of the local Infinity server.
  * A secondary lightweight NLI (Natural Language Inference) model (e.g., `mDeBERTa-v3-base-mnli-xnli`) will be hydrated alongside the existing embedding model.
  * If the mathematical confidence score for a specific label/agent exceeds a strict threshold (e.g., > 0.85), the request is routed instantly.

* **Stage 2: LLM Oracle (LiteLLM Fallback)**
  * If the input contains a visual payload (image).
  * OR if the Stage 1 text classification returns a low confidence score (indicating ambiguity).
  * The routing falls back to the existing LLM setup, leveraging its multimodal retinas and deep reasoning to break the tie.

## Consequences

### Positive
* **Latency Reduction:** Routing time for ~90% of daily interactions will drop from seconds to ~50ms.
* **Cost Efficiency:** Massive reduction in LiteLLM token consumption.
* **Capability Retention:** The system retains full multimodal awareness without compromising text-processing speed.

### Negative
* **Resource Overhead:** The `lifeos_embeddings` Docker container will require an additional ~500-800MB of RAM to keep the zero-shot classifier hydrated.
* **Complexity:** The `CrewOrchestrator` will require a slightly more complex routing logic block to handle the threshold evaluation and fallback mechanism.