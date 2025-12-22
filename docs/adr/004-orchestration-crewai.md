# [MADR] 004 - Orchestration Framework Strategy (CrewAI)

* **Status:** Accepted
* **Date:** 2025-12-21
* **Deciders:** David G. Calles
* **Technical Story:** Selection of the engine to manage multi-agent interactions.

## Context and Problem Statement

LifeOS relies on the coordination of multiple agents with specialized personalities and skills. We need an orchestration framework capable of managing these interactions efficiently.
We evaluated whether to implement a complex state-machine approach (Graph-based) or a role-playing organizational approach (Process-based).

## Decision Drivers

* **Structural Alignment:** LifeOS simulates a corporate hierarchy (a "Board of Directors" or Family Council), rather than a complex cyclic state graph.
* **Abstraction Level:** There is a strong requirement to define high-level "Roles", "Backstories", and "Tasks" in a human-readable format.
* **Maintainability:** Preference for declarative configuration (defining *what* needs to be done) over complex imperative flow control (defining exact state transitions).

## Considered Options

* **Option 1: LangGraph.** A library for building stateful, multi-actor applications with LLMs using graph structures.
* **Option 2: CrewAI.** A framework for orchestrating role-playing, autonomous AI agents.

## Decision Outcome

Chosen option: **Option 2: CrewAI**.

We are adopting CrewAI as the primary orchestration engine because its "Role-Playing" architecture maps 1:1 with the mental model of the LifeOS project (Specialized Agents, Tasks, Process).

### Positive Consequences

* **Separation of Concerns:** Enforces a clear definition of responsibilities (Single Responsibility Principle) per agent.
* **Native Process Support:** Out-of-the-box support for sequential and hierarchical processes without writing complex logic.
* **Tooling:** Clean integration with custom tools (as defined in ADR-001 regarding memory and utilities).

### Negative Consequences

* **Flexibility Trade-off:** Less flexibility for managing infinite loops or highly granular state transitions compared to pure graph-based solutions like LangGraph.

### Adaptation Strategy

While CrewAI is less granular than a graph, it is considered sufficient to implement the "Consensus/Debate" patterns required by the Family Council functionality without the overhead of maintaining a state machine.