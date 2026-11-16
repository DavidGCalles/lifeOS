"""Personas del edge: carga de personas/agents.yaml y render del prompt.

v3-FR-02a: la semilla agents.yaml NO se toca (es el salvamento del repo
viejo). La nota de fase la inyecta el runtime para que la persona no
alucine tools o memoria que todavía no existen en el edge.
"""
from pathlib import Path

import yaml

# personas/ vive en la raíz del repo, dos niveles arriba de src/bot/
PERSONAS_PATH = Path(__file__).resolve().parents[2] / "personas" / "agents.yaml"

FASE_NOTE = (
    "FASE v3-FR-02a (prototipo): en esta fase NO tienes herramientas ni "
    "memoria persistente. Responde conversacionalmente con el contexto que "
    "tienes. No anuncies guardados ni búsquedas: cuando existan, lo sabrás."
)


def load_personas() -> dict:
    with open(PERSONAS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def default_persona(personas: dict) -> dict:
    """Persona por defecto: Jane. Sin ella, la primera del yaml; sin yaml, nada."""
    if "jane" in personas:
        return personas["jane"]
    if personas:
        return next(iter(personas.values()))
    raise SystemExit(
        "personas/agents.yaml no define ninguna persona (se esperaba 'jane')."
    )


def render_system_prompt(persona: dict, current_user: str) -> str:
    parts = [
        (persona.get("backstory") or "").strip(),
        f"ROL: {persona.get('role', '')}",
        f"OBJETIVO: {persona.get('goal', '')}",
    ]
    text = "\n\n".join(p for p in parts if p)
    text = text.replace("{current_user}", current_user)
    return f"{text}\n\n{FASE_NOTE}"
