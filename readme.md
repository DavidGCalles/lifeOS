# 🔥 LifeOS v2 — Personal Governance OS (Status: Active Development)

**Última actualización:** 2026-02-03

**LifeOS** es un sistema de gobernanza personal basado en agentes autónomos (**CrewAI**) que ayudan a convertir intención en acción. No es un simple chatbot: es una arquitectura modular, autoalojada y orientada a privacidad que combina **enrutamiento de agentes**, **memoria dual (sesiones + vector DB)** y un **proxy de LLMs (LiteLLM)** para trabajar con modelos multimodales de forma segura y sustituible.

---

## 🚀 Novedades (Feb 2026)
- ✅ **Sensory Cortex (Multimodal)**: Soporte para **imágenes** (passthrough visual) y **notas de voz** (normalización + transcripción). Los inputs no textuales se procesan en `src/sensory` y se entregan a los agentes en un formato multimodal estándar.
- ✅ **Two-Speed / Fast Track**: Canal "rápido" para intents simples (FastTrack agents) y canal "profundo" para razonamiento costoso. Implementado en `src/fast_agents.py` y `src/crew_orchestrator.py`.
- ✅ **Proxy de LLMs (LiteLLM)** y **Memoria Semántica (Qdrant)** funcionando (configurable en `litellm_config.yaml`).

---

## 🏗️ Arquitectura y Conceptos Clave

- **CrewAI (Agents):** Agentes especializados declarados en `src/config/agents.yaml`. Cada agente tiene personalidad, herramientas y objetivos.
- **LiteLLM Proxy:** Abstracción para cambiar proveedores de modelo con una configuración central.
- **Memoria Dual:** `sessions.json` para contexto conversacional y **Qdrant** para memoria vectorial a largo plazo.
- **Identidad / RBAC:** `IdentityManager` protege la entrada y asigna roles (`ADMIN`, `FAMILY`, `GUEST`).
- **Sensory Cortex:** Middleware (`src/sensory/cortex.py`) que enruta `photo` y `voice` a drivers especializados (`VisualDriver`, `AudioDriver`).

---

## 🧩 Implementación de Multimodal (Detalles Técnicos)
- **Visual (Photos):** `VisualDriver` optimiza la imagen (resize + JPEG) y la codifica en Base64 para generar un payload multimodal compatible con LLMs modernos.
- **Audio (Voice Notes):** `AudioDriver` normaliza audio (OGG -> MP3 via `pydub`/FFmpeg), envía a un pool de transcripción (`audio-model`) y retorna la transcripción en texto para su procesamiento.
- **Routing:** La Dispatcher puede ser multimodal; por ejemplo, una foto del refrigerador se enruta al agente `Kitchen`.

> Tip: Para probar localmente, envía una foto o una nota de voz al bot en Telegram. Las notas de voz se transcriben y llegan como texto; las fotos llegan como payload multimodal.

---

## ✅ Requisitos e Instalación

### Requisitos del sistema
- Docker & Docker Compose (opcional para despliegue). 
- **FFmpeg** (requerido para normalizar audio). En Windows puedes instalarlo por choco o descargar binarios:
  - Chocolatey: `choco install ffmpeg`
  - Descargar desde https://ffmpeg.org/

### Python deps
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

> Nota: `pydub` requiere FFmpeg en PATH.

### Configuración mínima
- Crea `.env` con tus credenciales (ej. `GEMINI_API_KEY`, `TELEGRAM_TOKEN`).
- Añade `src/config/users.json` para los roles (o usa `users.json` en la raíz si prefieres).

### Levantar localmente (Docker)
```bash
docker-compose up -d --build
```

Logs útiles:
```bash
docker-compose logs -f lifeos
```

---

## 📂 Estructura del Proyecto (rápida)
```
lifeOS/
├── data/                  # Qdrant, sessions.json
├── docs/                  # Vision, PRD, ADRs
├── docker-compose.yml
├── litellm_config.yaml
├── main.py                # FastAPI + Telegram lifecycle + Sensory registrations
├── src/
│   ├── sensory/           # Sensory Cortex + drivers (visual, audio)
│   ├── crew_orchestrator.py
│   ├── fast_agents.py     # Fast Track agents
│   ├── memory_manager.py  # Qdrant integration
│   └── ...
└── requirements.txt
```

---

## 🛠️ Roadmap (Siguientes implementaciones)
```mermaid
graph TD
    %% DEFINICIÓN DE CLASES Y ESTILOS
    classDef urgent fill:#e74c3c,stroke:#c0392b,stroke-width:2px,color:#fff;
    classDef high fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#fff;
    classDef complex fill:#8e44ad,stroke:#2c3e50,stroke-width:2px,color:#fff;
    classDef done fill:#27ae60,stroke:#2ecc71,stroke-width:2px,color:#fff;

    %% --- FASE 1: PROTOCOLOS DE INTERACCIÓN ---
    subgraph Phase1 [Fase 1: Social Logic & Interaction]
        direction TB
        FR16_Logic(<b>FR-16: Group Governance Middleware</b><br/>Scope: main.py Routing<br/>Status: Ready to Dev):::urgent
        FR16_Logs(<b>Passive Interaction Logging</b><br/>Scope: SessionManager<br/>Status: Definition):::urgent
    end

    %% --- FASE 2: INGESTA DE DOCUMENTOS ---
    subgraph Phase2 [Fase 2: Deep Ingestion Service]
        direction TB
        FR17_Doc(<b>FR-17: Document Parser</b><br/>Scope: Sensory Cortex<br/>Input: Direct File Upload):::high
        FR17_Drive(<b>FR-17: External Source Connector</b><br/>Scope: Drive API Tools<br/>Input: Linked Resources):::high
    end

    %% --- FASE 3: ARQUITECTURA DE MEMORIA ---
    subgraph Phase3 [Fase 3: Unified Memory Core]
        direction TB
        ADR12_Interface(<b>ADR-012: Memory Abstraction Layer</b><br/>Refactors: FR-07, FR-08<br/>Target: Unified I/O):::complex
        ADR12_RAG(<b>Context Retention Policy</b><br/>Scope: Lifecycle Management<br/>Logic: Short-Term vs Long-Term):::complex
    end

    %% DEPENDENCIAS
    FR16_Logic --> FR16_Logs
    FR16_Logs --> FR17_Doc
    FR17_Doc --> FR17_Drive
    FR17_Drive --> ADR12_Interface
    ADR12_Interface --> ADR12_RAG

    %% FLUJO
    Start((START)) --> Phase1
    Phase3 --> End((Production))
```

---

## 🔗 Documentación y ADRs
- Vision: `docs/vision-document.md`
- Product Requirements: `docs/product-requirements-document.md`
- ADRs: `docs/adr/00*-*.md` (ej. `011-multimodal-strategy.md`)

---

## ⚠️ Disclaimer
Proyecto personal de ingeniería. Úsalo con precaución y responsabilidad; algunas capacidades planeadas (p.ej. actuadores financieros reales) requieren trabajo extra y validaciones legales antes de otorgar permisos de escritura automáticos.

Built with ❤️ and ☕ by David G. Calles.
