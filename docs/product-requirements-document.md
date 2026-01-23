# LifeOS v2: Product Requirements Document (PRD)
**"The Sovereign Home Office Manager Specification"**

| Metadata | Detail |
| :--- | :--- |
| **Version** | 1.0 |
| **Owner** | David G. Calles |
| **Status** | Living Specification |
| **Related Documents** | Vision Document v3.0, Architecture Decision Records (001-008) |

---

## 1. Introduction

### 1.1 Purpose
LifeOS is a personal governance system designed to eliminate the friction between **Human Intention** and **Operational Execution**. It is not a chatbot; it is a **Home Office Manager** that orchestrates the user's attention, memory, and assets (time, money, health) through an architecture of autonomous agents with data sovereignty.

### 1.2 Design Principles
1.  **Radical Sovereignty:** The user owns the infrastructure, models, and memory. No critical function depends on external black boxes.
2.  **Agency over Comfort:** The system prioritizes long-term goal achievement over immediate user satisfaction.
3.  **Invisible by Default:** The best interaction is the one that doesn't happen. The system must infer and execute, disturbing the user only for high-level confirmations.

---

## 2. Personas and Roles (RBAC)

The system implements strict access control (RBAC) to protect the core.

| Role | Code | Privileges | Implementation Reference |
| :--- | :--- | :--- | :--- |
| **The Sovereign** | `ADMIN` | Full access (R/W). System commands, financial management, debug logs. Access to "The Council". | |
| **The Circle** | `FAMILY` | Functional access (Limited R/W). Shopping lists, home automation, and shared calendar. No access to private memory. | |
| **The Outsider** | `GUEST` | Null or restricted access (Read-only/Sandboxed). The system applies evasive responses or direct blocking. | |

---

## 3. Cognitive Architecture (Functional Requirements)

### 3.1 Interface and Ubiquity
* **FR-01 (Zero-Friction Entry):** The primary entry point is instant messaging (Telegram) without explicit login, authenticating via User ID.
    * *Future Requirement:* Native support for ambient voice input (Ambient Mic) and wearables.
* **FR-02 (Intent Routing - Two Speed):** The system classifies intent in <200ms to decide the execution lane:
    * *Fast Track:* Immediate responses, phatic communication, and simple queries (Flash/Gemma Models).
    * *Slow Track:* Complex reasoning requiring tools or debate (Pro/Reasoning Models).

### 3.2 The Crew
The system operates through specialists configurable via YAML:
* **FR-03 (Jane - Chief of Staff):** Agenda management, coordination, and empathy.
* **FR-04 (Padrino - Discipline):** Habit supervision, stoicism, and behavioral correction.
* **FR-05 (Kitchen - Logistics):** Nutrition and stock management.
* **FR-06 (The Council - *Target*):** Internal debate protocol where multiple agents (e.g., Padrino vs. Jane) discuss a critical decision and present a synthesis to the user, rather than a single response.

### 3.3 Memory and Context (Total Recall)
* **FR-07 (Episodic Memory):** Vector storage (Qdrant) of facts, preferences, and past decisions. Agents must query this memory before acting (RAG).
* **FR-08 (Session Continuity):** Sliding context window to maintain coherence in immediate chat.
* **FR-09 (Passive Ingestion - *Target*):** Ability to process unstructured "brain dumps" (long audio/text), extract entities, and archive them silently without initiating a conversation.

---

## 4. Execution Capabilities (Effectors)

This section defines how the system impacts reality ("Skin in the Game").

### 4.1 Basic Tools (Read/Compute)
* **FR-10 (Time Awareness):** Precise awareness of local date/time for task validation.
* **FR-11 (Web Knowledge):** Access to web search for real-time data.
* **FR-12 (Calculator/Logic):** Precise mathematical computation capability for nutrition or finances.

### 4.2 Critical Effectors (Write/Act - *Target*)
* **FR-13 (Financial Sovereignty):** Integration with banking APIs (or headless automation) with write permissions. Capability to move funds to savings accounts or block transactions according to predefined rules.
* **FR-14 (Biological Firewall):** Integration with Home Assistant/Router. Capability to cut internet access or modify the environment (lights/temperature) to enforce sleep cycles or deep work.
* **FR-15 (Calendar Guard):** Capability to automatically reject incoming invitations and block time slots for "Deep Work" without user intervention.

---

## 5. Non-Functional Requirements (NFR)

### 5.1 Resilience and Infrastructure
* **NFR-01 (Model Agnosticism):** Total decoupling from the LLM provider via Proxy (LiteLLM). The system must be able to switch from Gemini to OpenAI or Anthropic just via configuration.
* **NFR-02 (Local Fallback - *Target*):** In case of internet outage or API failure, the system must degrade to a local model (Ollama/Llama) to maintain critical agenda and note-taking functions.

### 5.2 Privacy and Security
* **NFR-03 (Self-Hosted Storage):** All memory vectors and session logs must reside in Docker volumes controlled by the user or private Cloud instances (Firestore/Qdrant), never in shared public SaaS.
* **NFR-04 (Encrypted Vault - *Target*):** The biographical database must be encrypted at rest to guarantee that the user's "digital psyche" is not physically accessible.