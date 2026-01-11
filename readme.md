# 🔥 LifeOS v2: Sistema de Gobernanza Personal Multi-Agente

> *"Tu vida es un sistema. Diséñalo o sé un esclavo del diseño de otro." - Agente Jane*

**LifeOS v2** es un sistema de gobernanza personal basado en inteligencia artificial. No es un simple chatbot; es una arquitectura de **microservicios** que orquesta un equipo de agentes autónomos (**CrewAI**) diseñados para gestionar áreas críticas de la vida. El sistema opera a través de **Telegram**, utiliza un **Proxy de LLMs** para robustez y está dotado de un sistema de **memoria dual** (conversacional y vectorial) para recordar interacciones y hechos clave.

## 🏗️ Arquitectura y Conceptos Clave

El sistema está completamente dockerizado y se basa en 5 pilares fundamentales:

1.  **Orquestación de Agentes (CrewAI):** El núcleo del sistema. En lugar de un único modelo monolítico, LifeOS utiliza un "equipo" de agentes especializados (definidos en `src/config/agents.yaml`) con roles, herramientas y objetivos distintos. Un agente "enrutador" analiza la intención del usuario y delega la tarea al especialista adecuado.

2.  **Abstracción de LLM (LiteLLM):** Toda la comunicación con los proveedores de modelos (Google, OpenAI, etc.) se realiza a través de un proxy LiteLLM. Esto nos independiza del proveedor, permitiendo cambiar de modelo con una sola línea de YAML, establecer fallbacks automáticos y monitorizar costes de forma centralizada.

3.  **Sistema de Memoria Dual:**
    *   **Memoria Conversacional (Corto Plazo):** Un fichero `sessions.json` guarda las últimas interacciones de cada chat para mantener el contexto inmediato de la conversación (ej. "¿y qué opinas de *eso*?").
    *   **Memoria Semántica (Largo Plazo):** Utiliza una base de datos vectorial **ChromaDB** (con planes de migrar a **Qdrant**) para almacenar y recuperar recuerdos a largo plazo. Los agentes pueden guardar y consultar esta memoria usando herramientas RAG.

4.  **Identidad y RBAC (Middleware):** Un `IdentityManager` actúa como middleware en la entrada de cada mensaje. Verifica al usuario contra un fichero `users.json`, asigna un rol (`ADMIN`, `FAMILY`, `GUEST`) y enriquece el contexto. Esto permite personalizar las respuestas y asegurar que solo usuarios autorizados interactúen con el sistema.

5.  **Interfaz Conversacional (Telegram):** Se eligió Telegram por su robusta API de bots, su universalidad (móvil/escritorio) y por delegar la gestión de UI y autenticación, permitiendo al equipo centrarse exclusivamente en la lógica de los agentes.

## 🤖 El Equipo (The Crew)

El equipo de agentes está definido de forma declarativa en `src/config/agents.yaml`. Cada uno tiene una personalidad, un conjunto de herramientas y un objetivo muy específico.

| Agente | Rol | Objetivo |
| :--- | :--- | :--- |
| **Dispatcher** | Enrutador Central | Clasificar la intención del usuario y derivar al especialista correcto. |
| **Jane** | Chief of Staff & Guardian | Coordinar la vida familiar, gestionar la agenda y velar por el bienestar. |
| **Padrino** | Mentor de Disciplina | Mantener al usuario enfocado y libre de vicios usando lógica estoica. |
| **Kitchen** | Kitchen Chief | Optimizar la nutrición y energía adaptándose al stock de comida disponible. |

## 🚀 Instalación y Despliegue

### Requisitos previos
* Docker y Docker Compose instalados.
* Una API Key de un proveedor de LLM compatible (ej. Google Gemini).
* Un Token de Bot de Telegram (obtenido vía @BotFather).

### 1. Clonar el repositorio
```bash
git clone https://github.com/DavidGCalles/lifeOS.git
cd lifeOS
```

### 2. Archivos de Configuración
Crea los siguientes archivos en la raíz del proyecto:

*   **.env:** Para tus secretos.
    ```env
    # Credenciales del proveedor de LLM (se inyectan en el proxy)
    GEMINI_API_KEY=tu_api_key_de_google_aqui

    # Token del bot de Telegram (se inyecta en la app)
    TELEGRAM_TOKEN=tu_token_de_telegram_aqui
    ```
*   **users.json:** Para definir quién puede usar el bot y con qué rol.
    ```json
    [
      {
        "user_id": 123456789,
        "name": "David",
        "role": "ADMIN"
      },
      {
        "user_id": 987654321,
        "name": "Invitado",
        "role": "GUEST"
      }
    ]
    ```

### 3. Despliegue
Levanta la pila completa de servicios (App, Proxy LLM, Vector DB):

```bash
docker-compose up -d --build
```

La primera vez, la descarga de las imágenes puede tardar unos minutos. Una vez levantado, el bot estará operativo en Telegram.

Para ver los logs en tiempo real:
```bash
docker-compose logs -f lifeos
```

## 📂 Estructura del Proyecto
```
lifeOS/
├── data/
│   ├── chroma/             # Datos persistentes de la memoria vectorial
│   └── sessions.json       # Memoria conversacional de corto plazo
├── docs/
│   └── adr/                # Decisiones de arquitectura documentadas
├── docker-compose.yml      # Orquestación (App, LiteLLM, ChromaDB)
├── Dockerfile              # Imagen de la aplicación principal
├── litellm_config.yaml     # Configuración del Proxy (Modelos, fallbacks)
├── main.py                 # Punto de entrada (Telegram Handler + Middleware)
├── readme.md               # Esta guía
├── requirements.txt        # Dependencias de Python
└── src/
    ├── config/
    │   ├── agents.yaml     # Definiciones declarativas de los agentes
    │   ├── tasks.yaml      # Definiciones declarativas de las tareas
    │   └── users.json      # Allow-list de usuarios y roles
    ├── crew_orchestrator.py# Lógica de enrutamiento y ejecución de Crews
    ├── identity_manager.py # Middleware de Identidad y RBAC
    ├── memory_manager.py   # Gestor de la memoria vectorial (ChromaDB)
    ├── utils/
    │   └── session_manager.py # Gestor de la memoria conversacional
    └── tools/
        ├── memory_tool.py  # Herramienta para que los agentes usen la memoria
        └── ...             # Otras herramientas (búsqueda, calculadora, etc.)
```

## 🔮 Roadmap
- [x] **Arquitectura Multi-Agente:** Implementado con CrewAI.
- [x] **Proxy de LLMs:** Implementado con LiteLLM.
- [x] **Memoria Conversacional:** Implementada con `sessions.json`.
- [x] **Identidad y RBAC:** Implementado con `IdentityManager` y `users.json`.
- [x] **Memoria a Largo Plazo (v1):** Implementada con ChromaDB.
- [ ] **Migración de VectorDB:** Actualizar de ChromaDB a Qdrant para optimizaciones de producción.
- [ ] **"The Council":** Implementar lógica de debate y consenso entre agentes para decisiones complejas.
- [ ] **Despliegue en Cloud:** Crear configuración para despliegue en GCP (Cloud Run).

## ⚠️ Disclaimer
Este es un proyecto personal de ingeniería de software. Los agentes tienen instrucciones de comportamiento que pueden ser directas o "particulares" (ej. "Padrino"). El objetivo es la eficiencia, no necesariamente el confort. Úsese bajo su propio riesgo.

Built with ❤️ and ☕ by David G. Calles.