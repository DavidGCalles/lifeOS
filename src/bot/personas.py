"""Personas del edge: carga de personas/agents.yaml y render del prompt.

La semilla agents.yaml NO se toca (es el salvamento del repo viejo, con
su catálogo de tools LEGACY que aquí no existe). La nota de fase la
inyecta el runtime: desde v3-FR-02b declara las DOS tools de borde reales
(memory_save / memory_recall) y acota los nombres antiguos del catálogo.
"""
from pathlib import Path

import yaml

# personas/ vive en la raíz del repo, dos niveles arriba de src/bot/
PERSONAS_PATH = Path(__file__).resolve().parents[2] / "personas" / "agents.yaml"

FASE_NOTE = (
    "MEMORIA PERSISTENTE (fase v3-FR-02b): tienes DOS herramientas reales, "
    "memory_save y memory_recall — son tu única superficie; los nombres del "
    "catálogo antiguo (time, search, memory_core, calendar_core, drive_core, "
    "attendee_search, user_governance) NO existen en esta fase y no debes "
    "mencionarlos ni prometerlos.\n"
    "- memory_save(texto): guarda un hecho durable cuando el usuario pida "
    "recordar algo («recuérdame», «apunta», «no olvides») o afirme un dato "
    "explícito y duradero (preferencia, decisión, contacto, plan). Pide SIEMPRE "
    "una frase autocontenida, sin pronombres sin antecedente. El guardado se "
    "confirma al aceptarse el registro: confirma al usuario con naturalidad "
    "(«apuntado»), sin anunciar mecánica interna (registros, tareas, "
    "vectorización).\n"
    "- memory_recall(consulta): recupera lo guardado antes cuando el usuario "
    "pregunte por algo anterior o cuando un hecho previo sea relevante para "
    "responder. Si no devuelve nada, dilo tal cual: JAMÁS inventes "
    "recuerdos.\n"
    "Si una herramienta falla, dilo con naturalidad y ofrece reintentarlo. "
    "Además de esta memoria persistente sigues viendo la conversación "
    "reciente; lo demás funciona igual."
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
