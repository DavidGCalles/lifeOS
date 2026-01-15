# [ADR] 008 - Hybrid Two-Speed Architecture & Latency Optimization

* **Status:** Proposed
* **Date:** 2026-01-14
* **Deciders:** David G. Calles
* **Technical Story:** Post-deployment analysis revealed unacceptable latency (4+ minutes) for basic interactions due to the overhead of the orchestration framework.

## Context and Problem Statement

The current architecture treats every user interaction as a "Project" managed by CrewAI. This involves instantiating agents, tasks, and injecting heavy system prompts and tool definitions for every single turn of conversation.
While this works for complex reasoning (e.g., "Plan a week of meals based on stock"), it is catastrophic for:
1.  **Phatic Communication:** Greetings or simple questions ("Hello Jane", "What time is it?").
2.  **Routing:** The decision of *who* should handle the message.
3.  **User Experience:** Telegram users expect near-instant feedback, but the current stack imposes a multi-minute delay, leading to timeouts and frustration.

Furthermore, all agents currently share a single "Model List" in `litellm_config`, forcing the system to default to the most capable (and often slowest/most expensive) model for trivial tasks.

## Decision Drivers

* **Latency:** The "Time to First Token" (TTFT) for conversational interactions must be under 2 seconds.
* **Efficiency:** Trivial tasks (routing, chatting) should not consume heavy computational resources or massive context windows.
* **Cost:** We must stop using heavy reasoning models for classification tasks.
* **Control:** We need granular control over the context window, stripping away the verbose "thought process" injection of CrewAI when it's not needed.

## Considered Options

* **Option 1: Optimize CrewAI.** Try to strip down system prompts and use faster models within the framework. (Discarded: The framework overhead itself—instantiation, tool binding, loop management—is the bottleneck).
* **Option 2: Worker Pools Only.** Move everything to background workers. (Discarded: Solves the timeout crash, but doesn't solve the user waiting 4 minutes for a "Hello").
* **Option 3: Hybrid Two-Speed Architecture.** Extract the "Brain" (Router/Jane) from the "Muscle" (Specialist Crews).

## Decision Outcome

Chosen option: **Option 3: Hybrid Two-Speed Architecture**.

We will refactor the system to operate on two distinct tracks:

1.  **Fast Track (Synchronous / Real-Time):**
    * **Components:** `IdentityManager`, `Router` (Classifier), and `Jane` (Conversational/Generalist).
    * **Technology:** Direct calls to LiteLLM (via `openai` client) bypassing CrewAI entirely.
    * **Model:** Lightweight models (e.g., Gemini Flash, GPT-4o-mini).
    * **Goal:** Immediate response, simple tool usage (Calendar, Memory Read), and triage.

2.  **Slow Track (Asynchronous / Deep Work):**
    * **Components:** `Padrino`, `Kitchen`, `Researcher`.
    * **Technology:** CrewAI (existing implementation) wrapped in asynchronous background tasks (Cloud Run CPU allocation or Worker pattern).
    * **Model:** Reasoning models (e.g., Gemini Pro/Ultra, GPT-4o).
    * **Goal:** Complex multi-step reasoning, massive context ingestion, and state changes.

### Technical Implementation Plan

1.  **Model Segregation:** Update `litellm_config.yaml` to expose specific endpoints (e.g., `model/router`, `model/reasoner`) instead of a generic fallback list.
2.  **Router Extraction:** Rewrite the Dispatcher logic to use a simple structured prompt (JSON mode) via LiteLLM to classify intent.
3.  **Jane Refactor:** Convert Jane into a standard LLM chain (function calling enabled) for direct interaction.
4.  **Context Hygiene:** Implement a strict "Sliding Window" for the Fast Track, injecting only the last $N$ messages and essential user metadata, stripping framework boilerplate.

### Consequences

* **(+) Speed:** Basic interactions will become instant.
* **(+) Cost:** Significant reduction in token usage by removing CrewAI overhead for 80% of interactions.
* **(+) UX:** The user feels listened to immediately.
* **(-) Complexity:** The codebase now supports two different interaction patterns (Direct LLM vs. Agentic Framework), increasing maintenance cognitive load.
* **(-) State Management:** We must ensure the `SessionManager` correctly merges logs from both the Fast Track (immediate) and Slow Track (delayed).