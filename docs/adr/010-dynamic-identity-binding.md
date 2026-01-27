# Core Tools Expansion & Dynamic Identity Binding

* **Status:** Accepted
* **Date:** 2026-01-23
* **Deciders:** David G. Calles
* **Technical Story:** Enabling agents to interact with the real world (Google Workspace) and managing user identity mapping dynamically without manual configuration.

## Context and Problem Statement

LifeOS agents currently lack "hands" to manipulate real-world data outside of the chat session. The highest priority is **Calendar Management** (Scheduling, Reminders).
To integrate Google Calendar via a **Service Account** (as decided in previous discussions), the system needs to know the target Google Email associated with the current Telegram User.
Currently, this mapping is hardcoded or manually edited in Firestore/JSON. This creates friction and prevents new users (Family/Guests) from onboarding themselves. We need a flow where the bot can autonomously request, validate, and persist this mapping.

## Decision Drivers

* **Autonomy:** Agents must be able to schedule events without user intervention (Service Account).
* **Onboarding Experience:** The user should not need to edit database files to link their email. The bot should ask for it naturally.
* **Persistence:** The link between Telegram ID and Google Email must be stored permanently in Firestore.
* **Security:** We use Resource-Based Access Control (Delegation). The user must explicitly share their calendar with the Bot's Service Account email.

## Decision Outcome

**Chosen Strategy:** **Service Account Tooling with Lazy Identity Binding**.

1.  **Core Tools:** We will implement a `CalendarToolkit` (List/Add Events) backed by the Google Service Account.
2.  **Lazy Binding Flow:**
    * If an agent attempts to use a Calendar tool but the `UserContext.calendar_id` is missing, the tool will fail gracefully or the agent will be instructed to stop and ask the user: *"I need your Google email to access your calendar."*
    * We will implement a `UpdateProfileTool` (or specific `SetEmailTool`) that allows the agent to save the user's provided email into the Firestore User Document.
3.  **Instruction Protocol:** The agent will be capable of guiding the user to share their calendar with the specific Service Account email address.

### Positive Consequences

* **Zero-Config Deployment:** New users can start using the bot immediately; configuration happens via chat.
* **Full Automation:** Agents can manage time, the scarcest resource.
* **Scalability:** The `IdentityManager` becomes a read/write interface, paving the way for future preference storage (diet, location, etc.).

### Negative Consequences

* **Interaction Friction:** The first time a user asks for a calendar task, there will be a multi-step dialogue to set up permissions.
* **Privacy:** The bot technically has access to read the calendar events provided by the shared permissions.

## Addendum: Implementation Validation & CRUD Expansion
**Date:** 2026-01-27

### Context
The implementation of the **Calendar Toolkit** (List, Add, Delete, Update) has been completed to validate the proposed architecture. During development, a coupling issue was identified in `main.py` where context injection required manual modification of the controller for each new tool.

### Refactor & Validation Results
To address the coupling, a **Centralized Context Injection** pattern (`src/utils/tool_context.py`) was implemented.

1.  **Architecture Validation:** The complete CRUD cycle validates the *Service Account + Lazy Binding* strategy. The agent successfully acts on behalf of the user using the persistent link in Firestore.
2.  **Scalability:** The new architecture allows adding *any* tool requiring user identity (e.g., Google Drive, Gmail, Spotify) by simply registering it in the `CONTEXT_NEEDED` list. `main.py` remains closed to modification (Open/Closed Principle).
3.  **Safety First:** The "Delete" and "Update" tools implement strict ambiguity checks (refusing to act on >1 match), proving that autonomous agents can manage sensitive data safely if constraints are enforced at the tool level.

**Conclusion:** The core architecture is verified. The path is now open for the rapid integration of the rest of the Google Workspace ecosystem.