# ADR-011: Sensory Cortex & Multimodal Input Strategy

* **Status:** deployed
* **Date:** 2026-01-30
* **Deciders:** DavidGCalles
* **Technical Story:** [FR-02.2] Multimodal Perception (Eyes & Ears)

## Context and Problem Statement

LifeOS v2 is currently "deaf and blind". It operates exclusively on text inputs (`str`). However, the ubiquitous nature of a personal assistant requires supporting **Voice Notes** (for hands-free interaction) and **Images** (for high-bandwidth context capture).

Currently, sending a binary file (photo or audio) to the bot results in a silent failure or an error, as `main.py` and the Agents are not equipped to ingest non-text payloads.

We need a strategy to ingest, process, and route these signals. The challenge is deciding between **Semantic Normalization** (converting everything to text before it reaches the agent) vs. **Native Multimodal Handling** (passing raw data to the LLM).

## Decision Drivers

* **Ubiquity:** The user must be able to interact via Audio when typing is impossible.
* **Data Fidelity:** Visual inputs contain nuances that are lost in text descriptions. The system must preserve raw visual data for the reasoning engine to avoid "telephone game" information loss.
* **Decoupling:** Business logic (Agents) should not handle file parsing, format conversion, or `ffmpeg` complexity.
* **Standardization:** The system requires a unified payload format compatible with `LiteLLM` to maintain model agnosticism.

## Considered Options

* **Option 1: Decentralized Handling (Agent-Level).** Each agent (Jane, Kitchen) implements logic to download and parse files.
    * *Critique:* Violates Single Responsibility Principle (SRP). Leads to massive code duplication and fragility.
* **Option 2: Semantic Normalization (Text-Only Middleware).** Convert everything to text at the edge. Audio becomes Transcript; Image becomes Caption.
    * *Critique:* "Captioning" is lossy. A caption "A fridge with food" is useless to a Chef agent needing to identify specific ingredients.
* **Option 3: Sensory Cortex (Layered Middleware).** A dedicated input processing layer that standardizes payloads *before* they reach the Router, using a hybrid strategy (Normalize Audio / Pass-through Vision).

## Decision Outcome

Chosen option: **Option 3: Sensory Cortex (Layered Middleware)**.

We will implement a middleware layer in `src/utils/sensory.py` that intercepts non-text messages at the edge (`main.py`) and transforms them into a standardized format consumable by the LiteLLM Proxy.

### 1. The Auditory Pathway (Normalization Strategy)
* **Concept:** "The Universal Scribe".
* **Rationale:** Audio is a transport medium for language. The *content* is what matters, not the waveform.
* **Implementation:** `Telegram (.ogg)` -> `FFmpeg` -> `STT Service` -> `Text`.
* **Result:** The Router and Agents receive plain text. They are unaware the message was spoken.

### 2. The Visual Pathway (Native Pass-through Strategy)
* **Concept:** "Native Multimodal Payload".
* **Rationale:** Vision is context. Converting it to text (Captioning) destroys data. Modern LLMs (Gemini, GPT-4o) have native retinas.
* **Implementation:**
    1.  Download image to memory.
    2.  Encode to Base64 (or upload to secure internal storage).
    3.  Construct a standard OpenAI-compatible multimodal payload:
        ```json
        {
          "role": "user",
          "content": [
            { "type": "text", "text": "User context/caption..." },
            { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,..." } }
          ]
        }
        ```
* **Routing:** The **Dispatcher** model MUST be multimodal to "see" the image and route based on visual content (e.g., routing a photo of a fridge to *Kitchen*).

## Consequences

### Positive
* **High Fidelity:** Agents can reason about specific visual details (e.g., "Is this steak cooked medium-rare?") which a captioner would miss.
* **Clean Codebase:** Agents remain focused on logic. They receive a standardized List payload instead of raw binary files.
* **Future Proof:** The standardized payload is compatible with any modern multimodal LLM supported by LiteLLM.

### Negative
* **Model Constraints:** We can no longer use text-only models (like standard Llama 3 or DeepSeek-R1) for the **Router** or **Vision-Dependent Agents**. If a blind model is selected, the system will error out.
* **Latency & Cost:** Processing images natively consumes significantly more tokens and bandwidth than processing a text description. Audio transcription introduces a pre-processing delay.