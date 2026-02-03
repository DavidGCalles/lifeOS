# LifeOS v2: Product Requirements Document (PRD)
**"The Sovereign Home Office Manager Specification"**

| Metadata | Detail |
| :--- | :--- |
| **Version** | 1.1 |
| **Owner** | David G. Calles |
| **Status** | Living Specification |
| **Related Documents** | Vision Document v3.0, Architecture Decision Records (001-011) |

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
* **FR-02 (Multimodal Intent Routing & Two Speed):** The system is not text-only; it possesses a **Sensory Cortex** to perceive reality through different channels.
    * **Fast/Slow Track:** Classifies intent in <200ms to decide execution lane (Immediate vs Deep Reasoning).
    * **Visual Pathway (Eyes):** Native support for images (compressed/resized on the edge). The Router "sees" the image to dispatch (e.g., Photo of Fridge -> Kitchen Agent).
    * **Auditory Pathway (Ears):** Native handling of Voice Notes. Audio is normalized (ffmpeg) and transcribed verbatim before reaching the reasoning core.
* **FR-16 (Group Social Protocol):** Rules of engagement for collective spaces (`groups`, `supergroups`).
    * **Default Silence:** The system must ignore all messages NOT explicitly directed to it.
    * **Activation Triggers:** Strict activation only via Direct Mention (`@Bot`) or Reply to Bot Message.
    * **Passive Logging (The Fly on the Wall):** The system logs group interactions to `SessionManager` for context awareness but DOES NOT trigger the Reasoning Engine (LLM) to save costs and avoid intrusion.

### 3.2 The Crew
The system operates through specialists configurable via YAML:
* **FR-03 (Jane - Chief of Staff):** Agenda management, coordination, and empathy.
* **FR-04 (Padrino - Discipline):** Habit supervision, stoicism, and behavioral correction.
* **FR-05 (Kitchen - Logistics):** Nutrition and stock management.
* **FR-06 (The Council - *Target*):** Internal debate protocol where multiple agents discuss a critical decision.

### 3.3 Memory and Context (The Cognitive Core)
*The system acts as a persistent biographer and contextualizer, managing information across different time horizons.*

* **FR-07 (Semantic Retrieval / RAG):** The system must be able to recall past facts, preferences, and decisions that exceed the immediate context window.
    * **Requirement:** Upon receiving a query, the system must autonomously search its long-term knowledge base for relevant information before generating a response.
* **FR-08 (Context Lifecycle & Hygiene):** The system must actively manage the limited "working memory" (Context Window) to prevent saturation and hallucination.
    * **Requirement:** The system must differentiate between **Ephemeral Noise** (phatic chat, temporary logistics) and **Persistent Facts**. It must automatically summarize or "forget" the former while promoting the latter to Long-Term Memory.
* **FR-09 (Unified Memory Interface):** The system must provide a unified abstraction layer for memory operations, decoupling the agents from the storage backend.
    * **Requirement:** Agents should not decide *where* to store data (Session vs. Vector DB). They should simply "Save Memory," and the system determines the appropriate persistence layer based on the information's half-life.
* **FR-10 (Passive Ingestion / "The Brain Dump"):** The system must be capable of processing unstructured streams of consciousness without conversational turn-taking.
    * **Requirement:** The user can send long audio notes or text blocks (tagged as `#dump`). The system extracts key entities, tasks, and facts, archives them silently, and acknowledges receipt without initiating a chat flow.

### 3.4 Sensory Perception & Deep Ingestion (The Senses)
*The system must ingest and comprehend high-fidelity information sources beyond simple chat text.*

* **FR-17 (The Reader / Document Driver):** The system must possess the capability to read, parse, and understand dense external documentation to support decision-making.
    * **Direct File Parsing:** The system must accept `PDF`, `DOCX`, and `TXT` files directly uploaded to the interface. It must extract clean text, ignoring formatting artifacts, for immediate analysis by the agents.
    * **Remote Access (Cloud Drive):** The system must be able to resolve and access URLs pointing to authorized cloud documents (e.g., Google Docs/Drive) found within Calendar events (e.g., "Read briefing before meeting") or chat messages.
    * **Content Synthesis:** When presented with a large document, the system must be able to generate summaries, extract action items, or answer specific questions based *strictly* on the document's content (Grounding).

---

## 4. Execution Capabilities (Effectors)

This section defines how the system impacts reality ("Skin in the Game").

### 4.1 Basic Tools (Read/Compute)
* **FR-10 (Time Awareness):** Precise awareness of local date/time for task validation.
* **FR-11 (Web Knowledge):** Access to web search for real-time data.
* **FR-12 (Calculator/Logic):** Precise mathematical computation capability for nutrition or finances.

### 4.2 Critical Effectors (Write/Act - *Target*)
* **FR-13 (Financial Sovereignty):** Integration with banking APIs (or headless automation) with write permissions.
* **FR-14 (Biological Firewall):** Integration with Home Assistant/Router to modify environment (lights/internet) for habits.
* **FR-15 (Calendar Guard):** Capability to automatically reject incoming invitations and block time slots for "Deep Work" without user intervention.

---

## 5. Non-Functional Requirements (NFR)

### 5.1 Resilience and Infrastructure
* **NFR-01 (Model Agnosticism):** Total decoupling from the LLM provider via Proxy (LiteLLM).
* **NFR-02 (Local Fallback - *Target*):** Ability to degrade to a local model (Ollama/Llama) if the cloud goes down.

### 5.2 Privacy and Security
* **NFR-03 (Self-Hosted Storage):** All memory vectors and session logs must reside in user-controlled Docker volumes.
* **NFR-04 (Encrypted Vault - *Target*):** The biographical database must be encrypted at rest.