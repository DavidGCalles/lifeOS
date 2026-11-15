# LifeOS v3 — edge client de coreAI

Rama de rework greenfield (EPIC #156). Este repo es el EDGE: consume coreAI
como substrate via submodule + include. Cero GCP, todo on-prem.

## Arranque (v3-FR-01)

1. `scripts/bootstrap.sh` — materializa el submodule `coreAI/`
2. `cp coreAI/.envExample coreAI/.env` — edita `LOCAL_LLM_API_BASE` y passwords
3. `docker compose up -d` — levanta edge + coreAI (postgres, qdrant, litellm,
   infinity, core-mcp, worker-node, observabilidad)
4. `docker compose ps` — healthchecks en verde: memoria (postgres/qdrant),
   gateway LLM (litellm) y worker (worker-node)

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
