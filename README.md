# LifeOS v3 — edge client de coreAI

Rama de rework greenfield (EPIC #156). Este repo es el EDGE: consume coreAI
como substrate via submodule + include. Cero GCP, todo on-prem.

## Arranque (v3-FR-01 + v3-FR-02a)

1. `scripts/bootstrap.sh` — materializa el submodule `coreAI/`
2. `cp coreAI/.envExample coreAI/.env` — edita `LOCAL_LLM_API_BASE` y passwords
3. `cp .env.example .env` — pon `TELEGRAM_BOT_TOKEN` (de @BotFather) y, si
   quieres, `ALLOWED_CHAT_ID` (whitelist de chats 1:1)
4. `docker compose up -d` — levanta edge + coreAI (postgres, qdrant, litellm,
   infinity, core-mcp, worker-node, observabilidad) **+ edge-bot**
5. `docker compose ps` — healthchecks en verde: memoria (postgres/qdrant),
   gateway LLM (litellm), worker (worker-node) y edge-bot

## v3-FR-02a: loop del bot E2E (edge-bot)

Telegram 1:1 → Jane (persona por defecto, `personas/agents.yaml`) → LLM vía
gateway de coreAI (litellm, modelo `local-fallback`) → respuesta al chat.

- **Transporte:** long polling tras una interfaz (`src/bot/transport/`). Con
  `timeout=50` Telegram responde en cuanto llega el update; un webhook futuro
  sería otro módulo del mismo contrato (exige URL pública, fuera de on-prem).
- **Memoria efímera:** rolling window de los últimos 5 mensajes por chat, en
  RAM (`src/bot/ephemeral_memory.py`), módulo aislado y swapeable cuando
  llegue la memoria vía dispatch (v3-FR-02b). **El edge no persiste nada
  propio**: sin volúmenes ni DB.
- **Nota de arranque:** `edge-bot` espera a que `litellm` esté healthy, y el
  gateway a su vez espera a Infinity (la carga de kits tarda minutos la
  primera vez). No es un cuelgue: es gating.

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
  (`Dockerfile`), sin puertos publicados (solo llamadas salientes a Telegram
  y al gateway), logs a Loki con task-UUID por update.
