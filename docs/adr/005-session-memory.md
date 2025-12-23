# [MADR] 005: Conversational Session Management Strategy (JSON File)

* **Status:** Accepted
* **Date:** 2025-12-23
* **Deciders:** David G. Calles
* **Technical Story:** Immediate resolution of agent statelessness (amnesia) between messages.

## Context and Problem Statement

Currently, the agents are stateless. Every new message from the user instantiates a fresh `Crew` with zero knowledge of the immediately preceding interaction. 
This causes incoherent conversations where the bot forgets the subject (e.g., "He" or "It") mentioned seconds ago. We need a mechanism to store and retrieve the last $N$ interactions per user (Chat History) to maintain conversational flow.

## Decision Drivers

* **Simplicity:** The solution must be easy to implement and debug (human-readable storage).
* **Infrastructure Economy:** Avoid adding heavy dependencies like Redis for a single-user system.
* **Persistence:** The context must survive container restarts (e.g., `docker-compose down`).
* **Latency:** Retrieval must be instantaneous to not block the Telegram response loop.

## Considered Options

* **Option 1: In-Memory Dictionary (Python `dict`).** Fast but data is lost on restart.
* **Option 2: Redis Container.** Robust but adds 30MB+ RAM overhead and maintenance complexity.
* **Option 3: File-Based JSON Storage.** Persistent, simple, zero-infra.
* **Option 4: CrewAI Built-in Memory.** Uses local embeddings (Chroma), adding unnecessary complexity/latency for simple chat history.

## Decision Outcome

Chosen option: **Option 3: File-Based JSON Storage**.

We will implement a custom `SessionManager` that persists chat history to a local JSON file mapped to a Docker volume.

### Technical Implementation

1.  **Storage:** A `sessions.json` file located in the persistent data volume.
2.  **Structure:** Key-Value store where Key=`telegram_chat_id` and Value=`List[Interaction]`.
3.  **Logic (Sliding Window):** We will store only the last **10 interactions** (User + Assistant) to keep the context window efficient.
4.  **Injection:** The history string will be injected directly into the **Task Description** before the agent starts execution.

### Consequences

* **(+) Zero Infra Cost:** No need for Redis or external DBs.
* **(+) Persistence:** Context survives updates and restarts.
* **(+) Debuggability:** We can manually inspect `sessions.json` to see what the bot "remembers".
* **(-) Scalability:** Not suitable for high-concurrency multi-tenant SaaS (acceptable trade-off for personal LifeOS).