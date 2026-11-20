# LifeOS v3 — edge client de coreAI

Rama de rework greenfield (EPIC #156). Este repo es el EDGE: consume coreAI
como substrate via submodule + include. Cero GCP, todo on-prem.

## Arranque (v3-FR-01 + v3-FR-02a + v3-FR-02b)

1. `scripts/bootstrap.sh` — materializa el submodule `coreAI/`
2. `cp coreAI/.envExample coreAI/.env` — edita `LOCAL_LLM_API_BASE` y passwords
3. `cp .env.example .env` — pon `TELEGRAM_BOT_TOKEN` (de @BotFather) y, si
   quieres, `ALLOWED_CHAT_ID` (whitelist de chats 1:1)
4. `docker compose up -d` — levanta edge + coreAI (postgres, qdrant, litellm,
   infinity, core-mcp, worker-node, observabilidad) **+ edge-bot**
5. `docker compose ps` — healthchecks en verde: memoria (postgres/qdrant),
   gateway LLM (litellm), worker (worker-node) y edge-bot

> **Si ya tenías la imagen del bot buildada antes de v3-FR-02b**: esta fase
> añade el SDK MCP a `requirements.txt` → el arranque exige REBUILD
> (`docker compose build edge-bot && docker compose up -d --no-deps edge-bot`).

## Rebuild rápido del edge-bot (léelo ANTES de cualquier `--build`)

Con `include`, coreAI y el edge son UN solo proyecto: `docker compose up -d
--build <servicio>` aplica el build a TODO lo que el comando arranca,
dependencias incluidas (`edge-bot → litellm → infinity`). El build de
Infinity (copia de los kits de modelos al contexto de build) es el más caro
del stack y NO siempre sale de caché: un `--build` descuidado son ~10
minutos de build que no necesitas para tocar el bot.

- Primera puesta en marcha: `docker compose up -d` — builda las imágenes
  que falten (una sola vez).
- Iterar sobre código del edge: `docker compose build edge-bot` y luego
  `docker compose up -d --no-deps edge-bot`.
- Levantar solo el bot: `docker compose up -d edge-bot` (las dependencias ya
  corriendo no se tocan).
- A pelo, `docker compose up -d --build` (sin servicio) solo si de verdad
  toca rebuild de todo el stack.

## v3-FR-02a: loop del bot E2E (edge-bot)

Telegram 1:1 → Jane (persona por defecto, `personas/agents.yaml`) → LLM vía
gateway de coreAI (litellm, modelo `local-fallback`) → respuesta al chat.

- **Transporte:** long polling tras una interfaz (`src/bot/transport/`). Con
  `timeout=50` Telegram responde en cuanto llega el update; un webhook futuro
  sería otro módulo del mismo contrato (exige URL pública, fuera de on-prem).
- **Memoria efímera:** rolling window de los últimos 5 mensajes por chat, en
  RAM (`src/bot/ephemeral_memory.py`), módulo aislado y swapeable. **El edge
  no persiste nada propio**: sin volúmenes ni DB.
- **Nota de arranque:** `edge-bot` espera a que `litellm` esté healthy, y el
  gateway a su vez espera a Infinity (la carga de kits tarda minutos la
  primera vez). No es un cuelgue: es gating.

## v3-FR-02b: memoria vía dispatch MCP (#169)

Jane tiene DOS tools de borde (`src/bot/memory_tools.py`) que el edge
traduce a los contratos del substrato por MCP (`src/bot/mcp.py`, cliente
streamable HTTP contra `core-mcp:8000`, sesión por llamada, SDK pin
`mcp==2.1.1`):

- `memory_save(texto)` → `coreai_dispatch_task` (VECTORIZE_EVENT,
  `project=lifeos`). **Write-then-read** (ADR-005 del substrato): el
  dispatch aceptado YA es el acuse (task_id); la vectorización es
  background del worker y no se espera ni se verifica con search.
- `memory_recall(consulta)` → `coreai_search_context` (recall síncrono
  read-only, `project=lifeos`, top_k 5, umbral 0.7 del substrato;
  lista vacía = no-match honesto).

La persona NO ve la superficie cruda de core-mcp (6 tools, admin de DLQ
incluido): el mapeo fijo de dos entradas acota el rango de error del
modelo — aunque alucine argumentos o tools, al substrato solo pueden
salir estos dos dispatches con payload limpio (`extra=forbid` en ambos
contratos del substrato; el payload se construye clave a clave).

- **Loop de function calling:** bounded a `LLM_MAX_TOOL_ROUNDS` (default
  3). Cada ronda es un pase del LLM: con un modelo de razonamiento local
  (~20 s/pase) un "recuérdame X" ronda los 40 s. Al agotarse el cupo, el
  tools param se retira y el modelo responde con texto.
- **Fallos:** un error de core-mcp o un isError del substrato NO matan el
  loop ni se registran como turno: Jane lo comunica y ofrece reintentar.
- **Proyecto:** `LIFEOS_MEMORY_PROJECT` (default `lifeos`) namespacea las
  memorias de este inquilino en la unified memory de coreAI.
- **Tests:** `pip install -r requirements-dev.txt && pytest` — traducción
  hermética con el cliente MCP mockeado (`tests/test_memory_tools.py`),
  sin red ni coreAI corriendo.

### DoD de v3-FR-02b

- [ ] "Recuérdame X" por Telegram 1:1 → Jane guarda en coreAI vía dispatch
      (registro aceptado con task_id; vectorización por el worker)
- [ ] "¿Qué te dije de X?" → Jane recupera desde coreAI vía recall y responde
- [ ] El edge no tiene almacenamiento de memoria propio (la ventana efímera
      es contexto conversacional en RAM; la persistencia es solo la de coreAI)

### DoD de v3-FR-02a

- [ ] Escribir por Telegram 1:1 y recibir respuesta coherente de la persona por defecto
- [ ] El edge no persiste nada propio (sin memoria; como mucho estado de sesión efímero)

## DoD de v3-FR-01

- [ ] `docker compose up` levanta edge + coreAI sin credenciales GCP
- [ ] Healthchecks en verde: PG/Qdrant, litellm, worker
- [ ] Cero referencias a Cloud Build/Run/Scheduler/Firestore en el compose del edge

## Notas

- El gitlink del submodule se materializa con `scripts/bootstrap.sh` (un
  `git submodule add` local); el compose referencia `coreAI/docker-compose.yml`
  via `include`.
- Los healthchecks de qdrant/litellm/worker los define el compose del edge
  como override; coreAI no se modifica.
- `edge-bot` es el primer servicio propio del edge: build local
  (`Dockerfile`), sin puertos publicados (solo llamadas salientes a Telegram,
  al gateway y a core-mcp), logs a Loki con task-UUID por update.
