"""Tools de borde para la persona — v3-FR-02b (#169).

Traducción ACOTADA entre la superficie de la persona (2 tools) y los
contratos del substrato por MCP (diseño aprobado en el issue):

    memory_save(texto)      → coreai_dispatch_task
                              {task_type: vectorize_event,
                               task_payload: {content, project}}
    memory_recall(consulta) → coreai_search_context
                              {query, project}

La persona NO ve la superficie cruda de core-mcp (6 tools, admin de DLQ
incluido): el edge curar su superficie es parte de ser dueño del loop
interactivo (substrate, not a brain). El mapeo fijo acota el rango de
error del modelo: aunque el LLM alucine argumentos o tools, al substrato
solo pueden salir estos dos dispatches con payload limpio.

Contratos del substrato [REPO coreAI]: VECTORIZE_EVENT es extra=forbid
({content, project, domain, visibility}) y RecallTextRequest también
(extra=forbid, {query, project, top_k, score_threshold}) — por eso el
payload SE CONSTRUYE aquí clave a clave: jamás se reenvía el dict crudo
del modelo.

Semántica write-then-read (ADR-005): el dispatch YA ES el acuse
(task_id + status); la vectorización real es background del worker y
NO se espera ni se infiere del search.
"""
import json
import logging

from .mcp import SubstrateError

log = logging.getLogger("edge-bot.memory")

# top_k del recall: el default del substrato es 5; se fija explícito para
# que la persona sepa cuánto contexto recibe sin depender del default
RECALL_TOP_K = 5

# Superficie OpenAI que se declara al LLM en cada petición de chat
EDGE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "memory_save",
            "description": (
                "Guarda un hecho durable en la memoria persistente "
                "compartida. Úsala cuando el usuario pida recordar algo "
                "(«recuérdame...», «apunta...», «no olvides...») o afirme "
                "un dato explícito y duradero (preferencia, decisión, "
                "contacto, plan). El texto debe ser UNA frase "
                "autocontenida, sin pronombres sin antecedente: es "
                "exactamente lo que se recuperará en el futuro."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "texto": {
                        "type": "string",
                        "description": (
                            "El hecho a recordar, en una frase "
                            "autocontenida y afirmativa."
                        ),
                    }
                },
                "required": ["texto"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "memory_recall",
            "description": (
                "Recupera de la memoria persistente lo guardado o dicho "
                "antes. Úsala cuando el usuario pregunte por algo anterior "
                "(«¿qué te dije de...?», «¿te acuerdas de...?», «¿qué "
                "tengo pendiente de...?») o cuando un hecho previo sea "
                "relevante para la respuesta actual."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {
                        "type": "string",
                        "description": (
                            "Qué buscar en la memoria, en lenguaje natural: "
                            "el tema o el hecho concreto que interesa."
                        ),
                    }
                },
                "required": ["consulta"],
                "additionalProperties": False,
            },
        },
    },
]


class MemoryTools:
    """Ejecutor de las 2 tools de borde. Recibe el cliente MCP inyectado
    (testable: el transporte se mockea), no sabe nada de Telegram ni del LLM."""

    def __init__(self, client, project: str):
        self._client = client
        self._project = project

    async def execute(self, call: dict, task: str = "-") -> tuple[bool, str]:
        """Ejecuta UN tool_call del LLM. Devuelve (ok, texto_para_el_modelo).

        ok=False → fallo de tool: el texto del resultado se lo dice al
        modelo (Jane lo comunica), y el llamador marca el turno como no
        registrable. NINGÚN path lanza excepción: el loop del bot es
        inmortal por diseño (lección del 02a).
        """
        name = ((call.get("function") or {}).get("name")) or call.get("name")
        try:
            arguments = json.loads((call.get("function") or {}).get("arguments") or "{}")
            if not isinstance(arguments, dict):
                raise ValueError("los argumentos no son un objeto JSON")
        except (ValueError, TypeError) as e:
            return False, (
                f"Argumentos de tool inválidos ({type(e).__name__}: {e}). "
                "Vuelve a emitir la llamada con JSON válido o responde sin "
                "usar la herramienta."
            )

        dispatch = getattr(self, f"_tool_{name}", None)
        if dispatch is None:
            # la superficie es EXACTAMENTE las dos tools: cualquier otra
            # cosa que el modelo alucine no tiene traducción
            return False, (
                f"Herramienta desconocida: {name!r}. Tu superficie es "
                "exactamente memory_save y memory_recall."
            )

        raw_args = arguments.get("texto") if name == "memory_save" else arguments.get("consulta")
        if not isinstance(raw_args, str) or not raw_args.strip():
            return False, (
                f"Falta el argumento de texto de {name} (vacío o de tipo "
                "incorrecto). Vuelve a emitir la llamada con el texto."
            )
        raw_args = raw_args.strip()

        try:
            return True, await dispatch(raw_args, task)
        except SubstrateError as e:
            log.error("task=%s tool=%s fallo de substrato: %s", task, name, e)
            return False, (
                f"Fallo hablando con la memoria persistente: {e}. "
                "Comunícalo al usuario con naturalidad y ofrele reintentar."
            )
        except Exception as e:
            # defensa final: nada de una tool puede tumbar el loop
            log.exception("task=%s tool=%s excepción no prevista", task, name)
            return False, (
                f"Fallo inesperado en {name} ({type(e).__name__}: {e}). "
                "Comunícalo al usuario con naturalidad."
            )

    # --- memory_save -----------------------------------------------

    async def _tool_memory_save(self, texto: str, task: str) -> str:
        # payload construido clave a clave (extra=forbid en el contrato):
        # argumentos de más del modelo NUNCA llegan al substrato
        payload = {"content": texto, "project": self._project}
        raw = await self._client.call(
            "coreai_dispatch_task",
            {"task_type": "vectorize_event", "task_payload": payload},
            task,
        )
        try:
            data = json.loads(raw)
            task_id, status = data["task_id"], data["status"]
        except (ValueError, KeyError, TypeError) as e:
            raise SubstrateError(
                f"respuesta de dispatch con forma inesperada "
                f"(esperaba task_id y status): {type(e).__name__}: {e} — "
                f"raw: {raw[:200]}"
            ) from e
        log.info(
            "task=%s memory_save ok: registro aceptado por la frontera "
            "(substrato task_id=%s status=%s, vectorizacion en background)",
            task, task_id, status,
        )
        # write-then-read (ADR-005): el dispatch ACEPTADO es el acuse; no se
        # espera al worker ni se verifica con search. El texto se lo da al
        # modelo para que confirme al usuario con naturalidad.
        return (
            f"Registrado: la memoria ha aceptado el hecho "
            f"(registro {task_id}, estado {status}; la indexación completa "
            "ocurre en segundo plano, NO la verifiques ni la anuncies). "
            "Confirma al usuario de forma natural."
        )

    # --- memory_recall ---------------------------------------------

    async def _tool_memory_recall(self, consulta: str, task: str) -> str:
        raw = await self._client.call(
            "coreai_search_context",
            # RecallTextRequest es extra=forbid: solo claves del contrato
            {"query": consulta, "project": self._project, "top_k": RECALL_TOP_K},
            task,
        )
        try:
            hits = json.loads(raw).get("hits") or []
        except (ValueError, TypeError) as e:
            raise SubstrateError(
                f"respuesta de recall con forma inesperada: "
                f"{type(e).__name__}: {e} — raw: {raw[:200]}"
            ) from e
        if not hits:
            # no-match honesto del substrato (umbral 0.7): lista vacía NO
            # es fallo — la memoria no miente con resultados flojos
            log.info("task=%s memory_recall sin resultados: %r", task, consulta[:80])
            return (
                "Sin resultados en la memoria persistente para esa "
                "consulta. Dilo tal cual; NO inventes recuerdos."
            )
        lines = []
        for hit in hits:
            content = (hit.get("content") or "").strip() or "(sin texto)"
            score = hit.get("score")
            score_txt = f"{score:.2f}" if isinstance(score, (int, float)) else "?"
            lines.append(f"- {content} (similitud {score_txt})")
        log.info(
            "task=%s memory_recall %d hits para %r", task, len(hits), consulta[:80]
        )
        return (
            "La memoria persistente devolvió estos registros:\n"
            + "\n".join(lines)
            + "\nÚsalos para responder; cita lo relevante y no añadas "
            "datos que no estén ahí."
        )
