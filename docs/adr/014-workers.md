# ADR-014: Background Workers & System State Awareness

## Status
Accepted

## Context
Following the implementation of the Unified Memory Layer (ADR-012), the system requires a mechanism to execute token-intensive background tasks (e.g., Context Retention & Hygiene, Document Parsing) without degrading the real-time user experience in the *Fast Track*.

Initial architecture discussions favored separating these tasks into an asynchronous worker. However, a critical flaw was identified regarding **Edge/Local deployments**. Local LLM servers (e.g., LM Studio, llama.cpp) process requests sequentially by default. If a "blind" background worker monopolizes the local LLM for a 45-second memory consolidation task, any incoming Telegram message will be queued, completely freezing the bot's real-time responsiveness and defeating the purpose of the Fast Track.

We need a background task strategy that respects Dev/Prod parity, avoids heavy infrastructure bloat (no Redis/Celery), and actively protects the local hardware queue.

## Decision
We will implement a **"One Image, Two Faces" (Webhook Cron)** architecture, protected by a new **State Awareness** layer.

### 1. The Webhook Cron Pattern
LifeOS will remain a single compiled Docker image but will be deployed as two logical services:
* **The Bot:** Synchronous, lightweight, dedicated to the Telegram webhook and fast orchestration.
* **The Worker:** Asynchronous, exposing internal HTTP endpoints protected by a `SYSTEM_CRON_TOKEN`.
* **Execution:** Instead of maintaining active background threads, scheduled jobs (via `docker-compose` curl loops in Edge, or Cloud Scheduler in GCP) will trigger the worker's endpoints during specific "dream cycles" (e.g., 03:00 AM).

### 2. The `SystemStatus` Interface
To prevent the worker from blindly blocking resources, we will introduce a new core component: `SystemStatus`. This class will act as the global pulse-checker for the system's operational environment.

* **Core Capability:** It will include methods such as `is_channel_active(time_window_minutes: int) -> bool`, which checks the `SessionManager` to verify if the user has recently interacted with the bot.
* **The "Educated Worker" Policy:** Before initiating any heavy LLM task, the worker **MUST** consult `SystemStatus`. If the system is deemed "Awake" (active user communication), the worker will gracefully abort the consolidation process and defer it to the next scheduled cycle. Consolidation will only occur during verified silence.

## Consequences

### Positive
* **Edge Resilience:** The Fast Track remains pristine and unblocked during local deployments. The worker respects the hardware limitations.
* **Centralized Awareness:** The `SystemStatus` interface establishes a scalable pattern for future health checks (e.g., API rate limits, network availability, or hardware thermal throttling).
* **Zero Bloat & Dev/Prod Parity:** No third-party message brokers are introduced. The codebase behaves consistently across local and cloud environments.

### Negative
* **Delayed Consolidation:** Because the worker will abort if the user is active, memory consolidation is strictly eventually-consistent and may be delayed if the user interacts with the bot during scheduled cron windows.
* **Deployment Updates:** The CI/CD pipeline and `docker-compose.yml` must be updated to handle the deployment of the dual-service configuration.