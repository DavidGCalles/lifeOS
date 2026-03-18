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

# Post-Implementation Review: [ADR-015] Two-Stage Router and Zero-Shot Fallback

## 1. Executive Summary
The implementation of ADR-015 has been successfully completed. The primary objective was to optimize the system's most critical latency bottleneck: initial routing decisions. To achieve this, a "Two-Stage" architecture was designed and integrated, prioritizing an ultra-fast NLI classification model and reserving generative LLM reasoning strictly as a structured fallback mechanism. Additionally, the UX friction caused by agent "double-talk" has been definitively resolved through the implementation of a strict silence protocol.

## 2. Core Architectural Changes Implemented

### 2.1. Two-Stage Routing Architecture (`CrewOrchestrator`)
The core logic of the orchestrator has been overhauled to separate routing into two distinct stages, avoiding costly and slow API calls when they are unnecessary:
* **Stage 1 (Zero-Shot Routing):** Standard text requests are first processed through a rapid classification layer using the `ZeroShotClient` (via `asyncio.to_thread`). If the input intent is clear and the confidence score is high, the system immediately deduces the target agent, completely bypassing generative LLM inference.
* **Stage 2 (LLM Fallback / Dispatcher):** If the Zero-Shot classification yields low confidence, or if the initial input contains multimodal context (e.g., images injected from the sensory cortex), the classic routing mechanism is activated. The `dispatcher` agent performs a dynamic "hot-swap" to a vision model when required. To prevent failures at this stage, a highly resilient JSON extraction process using regex (`_clean_and_extract_json`) was implemented, guaranteeing a safe fallback (defaulting to `JANE` if parsing fails).

### 2.2. Strict Silence Protocol (Kill Switch)
To prevent agents from generating redundant conversational summaries after offloading cognitive load to a tool (e.g., `delegate_deep_thought`), a total interrupt chain was established across the stack:
1. **Early Detection (`fast_agents.py`):** If any executed tool returns the exact token `TOOL_HANDOFF_COMPLETE_DO_NOT_REPLY`, the iterative reasoning loop is instantly broken, ignoring any remaining turns.
2. **Safe Propagation (`crew_orchestrator.py`):** Both the modern Fast Track and Legacy execution flows identify the token and immediately abort any secondary formatting.
3. **Interface Interception (`main.py`):** The main messaging loop acts as the final barrier. Upon detecting the control token, it executes a silent `return` for the session. This prevents Telegram from dispatching empty messages and stops the memory gateway from polluting the short-term working memory with garbage logs.

## 3. Technical Debt Resolved
* **Routing Latency:** Eliminated the need to consume LLM quota and wait times for ~80% of basic plain-text queries by delegating them to the local/dedicated NLI model.
* **Parser Stability:** Mitigated the reliance on "perfect" JSON responses from the LLM dispatcher through iterative Markdown cleaning and strict string formatting safeguards.

## 4. Status & Next Steps
* **ADR-015 Status:** **CLOSED / IMPLEMENTED**
* **Blockers:** None.
* **Next Objective:** With the orchestrator now stable, rapid, and strictly silent when required, the foundation is clear to tackle **[ADR-014] Background Workers**, expanding the system's deferred and scheduled execution capabilities.