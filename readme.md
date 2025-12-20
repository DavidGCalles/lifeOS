# 🔥 LifeOS v2: Sistema de Agentes Autónomos Distribuidos

> *"La vida es una mierda, arréglalo." - Agente Padrino*

**LifeOS v2** es un sistema de gobernanza personal basado en inteligencia artificial. No es un simple chatbot; es una arquitectura de **microservicios** que orquesta un equipo de agentes autónomos (**CrewAI**) diseñados para gestionar áreas críticas de la vida (salud, disciplina, finanzas) a través de una interfaz de **Telegram**.

A diferencia de las implementaciones estándar, LifeOS utiliza un patrón de **Proxy Inverso de LLM** (LiteLLM) para desacoplar la lógica de negocio del proveedor de inteligencia artificial, garantizando robustez, control de costes y estandarización de protocolos.

## 🏗 Arquitectura

El sistema corre completamente dockerizado y sigue una arquitectura limpia donde el núcleo de la aplicación (Python/CrewAI) se comunica con un servidor Proxy (LiteLLM) mediante el protocolo estándar de OpenAI, y este a su vez gestiona la conexión con los proveedores finales (Google Gemini, OpenAI, Anthropic).

### Tecnologías Clave
* **Orquestación:** [CrewAI](https://www.crewai.com/) (Agentes, Tareas, Procesos).
* **LLM Gateway:** [LiteLLM](https://docs.litellm.ai/) (Estandarización de API, Fallbacks, Rate Limiting).
* **Infraestructura:** Docker & Docker Compose.
* **Interfaz:** Python Telegram Bot (Asynchronous).
* **Modelos Actuales:** Gemini 2.0 Flash / Pro (vía Proxy).

## 🤖 El Equipo (The Crew)

El sistema no responde como un asistente genérico, sino que enruta la intención del usuario a especialistas con personalidades y reglas estrictas:

| Agente | Rol | Personalidad | Objetivo |
| :--- | :--- | :--- | :--- |
| **Dispatcher** | Enrutador | Invisible/Calculador | Analizar la intención semántica y derivar tráfico. |
| **El Padrino** | Disciplina | *Tough Love* / Estoico | Gestión de vicios (tabaco), dopamina y disciplina férrea. |
| **Kitchen Chief** | Nutrición | Chef Ejecutivo / Pragmático | Optimización energética y gestión de stock de cocina. |
| **Jane** *(WIP)* | Chief of Staff | Omnipresente / Empática | Coordinación familiar, agenda y consenso entre agentes. |

## 🚀 Instalación y Despliegue

### Requisitos previos
* Docker y Docker Compose instalados.
* Una API Key de Google (Gemini) o cualquier proveedor soportado.
* Un Token de Bot de Telegram (vía @BotFather).

### 1. Clonar el repositorio
```bash
git clone https://github.com/DavidGCalles/lifeOS.git
cd lifeos
```

### 2. Configuración de Entorno
Crea un archivo .env en la raíz del proyecto (basado en el ejemplo):
```
# Credenciales
TELEGRAM_TOKEN=tu_token_de_telegram_aqui
GEMINI_API_KEY=tu_api_key_de_google_aqui

# Configuración de Infraestructura
LITELLM_URL=http://litellm:4000
```

### 3. Configuración del Modelo (Opcional)
El archivo litellm_config.yaml define qué modelos se usan y las estrategias de fallback. Por defecto está configurado para usar gemini-2.0-flash simulando ser un endpoint de OpenAI.

### 4. Despliegue
Levanta los servicios (App + Proxy):

```
docker-compose up -d --build
```

Verifica que los agentes están operativos revisando los logs:

```
docker-compose logs -f lifeos
```

# 📂 Estructura del Proyecto
```
lifeos/
├── docker-compose.yml      # Orquestación de contenedores (App + LiteLLM)
├── Dockerfile              # Definición de la imagen de Python
├── litellm_config.yaml     # Configuración del Proxy (Modelos, Rate Limits)
├── main.py                 # Punto de entrada (Telegram Handler)
├── requirements.txt        # Dependencias (optimizadas para evitar conflictos)
└── src/
    ├── crew_agents.py      # Definición de Personalidades (Prompts)
    ├── crew_orchestrator.py# Lógica de enrutamiento y ejecución de Crews
    ├── tasks.py            # Definición de Tareas y Outputs esperados
    ├── llm_config.py       # Configuración del cliente LLM (apunta al Proxy)
    ├── config.py           # Gestión de variables de entorno
    └── utils.py            # Herramientas de diagnóstico (Radar de Modelos)
```

# 🔮 Roadmap
[x] Fase 1: Migración a Arquitectura Limpia (Eliminación de LangChain).

[x] Fase 2: Implementación de LiteLLM Proxy estable.

[ ] Fase 3: Despliegue de Jane (Identidad Central) y Agentes de Finanzas/Fitness.

[ ] Fase 4: Implementación de "The Council" (Lógica de debate y consenso entre agentes).

[ ] Fase 5: Memoria a Largo Plazo (Persistencia vectorial de contexto familiar).

[ ] Fase 6: Modo Invitado (RBAC para demos a terceros/recruiters).

# ⚠️ Disclaimer
Este es un proyecto personal de ingeniería de software aplicado a la productividad. Los agentes tienen instrucciones de comportamiento que pueden resultar abrasivas ("Padrino"). Úsese bajo su propio riesgo emocional.

Built with ❤️ and ☕ by David G. Calles.