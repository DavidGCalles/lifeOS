# [MADR] 006 - Identity & RBAC Strategy (Middleware Pattern)

* **Status:** Accepted
* **Date:** 2025-12-24
* **Deciders:** Technical Architecture Lead
* **Technical Story:** Transition from a single-user prototype to a multi-user Family Governance System.

## Context and Problem Statement

LifeOS v2 is evolving from a personal tool into a multi-user governance system. Currently, the system operates on a "blind trust" basis: it accepts messages from any Telegram user who interacts with the bot or naively extracts metadata without validation.

This poses two critical issues:
1.  **Security:** Unauthorized users could consume API tokens or invoke sensitive agents.
2.  **Context:** Agents cannot distinguish between users. Nutritional requirements, tone of voice, and access rights must be personalized per user profile.

We need a mechanism to identify, authenticate, and authorize users before the message reaches the reasoning core (CrewAI).

## Decision Drivers

* **Security:** Strict prevention of unauthorized access and protection of API quotas.
* **Personalization:** Enabling agents to access specific user profiles (e.g., specific dietary restrictions or goals per user).
* **Abstraction:** The agent logic must remain agnostic of the communication channel. It should receive a standardized `UserContext` object rather than raw API payloads.
* **Simplicity:** Avoid implementing full OAuth/Database infrastructure in the initial phase.

## Considered Options

* **Option 1: Hardcoded Logic.** Conditional checks inside the codebase. (Discarded: High technical debt, unmaintainable).
* **Option 2: Relational Database.** Full user/session management via SQL. (Discarded: Over-engineering for Phase 1).
* **Option 3: Middleware Pattern with Configuration Allowlist.** Intercept requests to inject context based on a loaded configuration.

## Decision Outcome

Chosen option: **Option 3: Middleware Pattern with Configuration Allowlist**.

We will implement an `IdentityManager` class acting as middleware. This decouples authentication from business logic.

### Roles Strategy

* **ADMIN:** Full system access, Debug Mode enabled, access to sensitive financial/admin modules.
* **FAMILY:** Full functional access (Home automation, Agenda, etc.), but shielded from system logs and strictly private admin modules.
* **GUEST:** Read-only access or restricted interaction window (for demos or temporary users).

### Storage Strategy

* **Phase 1 (Current):** Static configuration via Environment Variables or a secure `users.json` allowlist.
* **Phase 2 (Future):** Migration to a Vector/Relational DB once Long-Term Memory is fully established.

## Technical Implementation

The implementation follows the **"Clean Hack"** strategy:

1.  **Orchestration Interception:** The system intercepts the effective user ID at the entry point (`main.py`) before invoking the Orchestrator.
2.  **Identity Resolution:** The `IdentityManager` validates the ID against the Allowlist.
3.  **Context Hydration:**
    * **If Known:** A `UserContext` object is instantiated containing `{Name, Role, Preferences}`.
    * **If Unknown:** Execution is blocked, or a restricted `GUEST` role is assigned based on configuration.
4.  **Injection:** The `UserContext` is injected into the agents' execution loop.

### Consequences

* **(+) Rich Context:** Agents receive a semantic object (`UserContext`), decoupling them from implementation details.
* **(+) Security:** Default-deny policy for unknown users.
* **(+) Auditability:** System logs reflect the actor's identity, enhancing traceability.
* **(-) Maintenance:** Adding new users requires configuration updates (acceptable for a private governance system).