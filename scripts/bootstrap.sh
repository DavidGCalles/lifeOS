#!/usr/bin/env bash
# LifeOS v3 — v3-FR-01: materializa el submodule coreAI (gitlink + clone) si falta.
# Uso: scripts/bootstrap.sh   (idempotente)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

if ! git ls-files -s -- coreAI | grep -q '^160000'; then
  git submodule add https://github.com/DavidGCalles/coreAI.git coreAI
fi
git submodule update --init --recursive

echo "OK: submodule coreAI listo en ./coreAI"
echo "Siguiente: cp coreAI/.envExample coreAI/.env  (edita LOCAL_LLM_API_BASE y passwords)"
echo "          docker compose up -d"
