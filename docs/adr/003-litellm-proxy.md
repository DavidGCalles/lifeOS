# [MADR] 003 - LLM Abstraction Strategy (LiteLLM Proxy)

* **Status:** Accepted
* **Date:** 2025-12-21
* **Deciders:** David G. Calles
* **Technical Story:** Selection of the interface layer between LifeOS and AI Model Providers.

## Context and Problem Statement

Direct integration with provider-specific SDKs (e.g., `google-generativeai` or `openai-python`) creates strong coupling (Vendor Lock-in).
LifeOS requires resilience against price fluctuations, aggressive rate-limits, or sudden model unavailability. The core application logic must remain stable even if the underlying intelligence provider changes.

## Decision Drivers

* **Decoupling:** Business logic (Agents) must remain agnostic of the underlying provider (Google, OpenAI, Anthropic).
* **Standardization:** Requirement for a unified I/O protocol (Standard OpenAI format) to simplify agent code and library compatibility.
* **Resilience:** Requirement for automatic Fallbacks (e.g., if Gemini API fails, automatically failover to GPT-4 or a local Llama model).
* **Observability:** Need for centralized control over costs, logs, and debugging traces.

## Considered Options

* **Option 1: Direct SDK Integration.** Using native libraries for each provider within the agent code.
* **Option 2: Code-Level Abstraction (LangChain).** Using a Python library wrapper to handle switching.
* **Option 3: API Gateway Pattern (LiteLLM Proxy).** Running a standalone proxy server that standardizes all traffic to an OpenAI-compatible endpoint.

## Decision Outcome

Chosen option: **Option 3: API Gateway Pattern (LiteLLM Proxy)**.

We are implementing LiteLLM as an intermediate container (Proxy) between the application and the Large Language Models. This treats "Intelligence" as a microservice rather than a code dependency.

### Positive Consequences

* **Zero-Code Model Swapping:** Changing the active model is done via YAML configuration; no Python code changes or deployments are required.
* **Transparent Resilience:** Fallbacks and retries are managed by the proxy. The application remains unaware of upstream failures.
* **Protocol Unification:** All agents speak the "OpenAI Standard Dialect," regardless of whether the backend is Google Gemini, Anthropic Claude, or Ollama.

### Negative Consequences

* **Infrastructure Complexity:** Introduces a new component (container) in the stack that must be managed.
* **Latency:** Introduces marginal network latency (negligible compared to LLM inference time).