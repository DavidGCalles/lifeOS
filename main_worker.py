''' Workers api'''
import os
import logging
import json
from fastapi import FastAPI, Request, Depends, HTTPException
from pydantic import BaseModel, ValidationError

from src.memory_gateway import MemoryGateway
from src.crew_orchestrator import CrewOrchestrator
from src.schemas.memory import (
    EpisodicMemoryItem,
    EpisodicMemoryMetadata,
    MemoryDomainType,
    MemoryVisibility,
    MemoryCategory,
    MemoryType,
    MemorySource,
)
from src.identity_manager import IdentityManager
from src.system_status import SystemStatusManager


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
SYSTEM_CRON_TOKEN = os.getenv("SYSTEM_CRON_TOKEN")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
if not SYSTEM_CRON_TOKEN:
    logger.warning("SYSTEM_CRON_TOKEN is not set. Worker cron endpoints will be insecure.")
if not INTERNAL_API_KEY:
    logger.warning("INTERNAL_API_KEY is not set. Worker task endpoints will be insecure.")

# --- Globals ---
memory_gateway = MemoryGateway()
orchestrator = CrewOrchestrator(memory_gateway=memory_gateway)


# --- FastAPI App ---
app = FastAPI()

# --- Security Dependencies ---
async def verify_cron_token(request: Request):
    """Dependency to verify the cron token for scheduled tasks."""
    if not SYSTEM_CRON_TOKEN:
        logger.warning("Allowing cron request without token verification (dev mode).")
        return
    token = request.headers.get("X-Cron-Token")
    if token != SYSTEM_CRON_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing cron token")

async def verify_internal_api_key(request: Request):
    """Dependency to verify the internal API key for inter-service calls."""
    if not INTERNAL_API_KEY:
        logger.warning("Allowing internal request without API key verification (dev mode).")
        return
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Invalid or missing Authorization header")
    token = auth_header.split(" ")[1]
    if token != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal API key")


async def verify_system_readiness():
    """
    Dependency to verify that the system is in an optimal state for heavy tasks.
    Checks for recent user activity and LLM proxy health.
    """
    if await SystemStatusManager.is_channel_active(time_window_minutes=5):
        logger.warning("Aborting consolidation: Channel is active.")
        raise HTTPException(
            status_code=429,
            detail="System is busy with user activity. Task deferred.",
        )


# --- Worker Endpoints ---
@app.post(
    "/system/cron/consolidate",
    dependencies=[Depends(verify_cron_token),
                  Depends(verify_system_readiness)],
)
async def consolidate_memory():
    """
    Endpoint to trigger memory consolidation with semantic deduplication.
    """
    logger.info("Received request to consolidate memory.")

    # --- FASE 1: RECOLECCIÓN (Fetch Unconsolidated) ---
    unconsolidated_sessions = await memory_gateway.fetch_unconsolidated_sessions()

    if not unconsolidated_sessions:
        return {"status": "success", "message": "No unconsolidated memories found."}

    total_facts_saved = 0
    total_facts_discarded = 0
    processed_sessions = []

    for session_id, messages in unconsolidated_sessions.items():
        if not messages:
            continue

        owner_id = messages[0].get("metadata", {}).get("owner_id")
        if not owner_id:
            logger.warning(
                "Skipping session %s due to missing owner_id in the first message.",
                session_id,
            )
            continue

        user_ctx = await IdentityManager.get_user(owner_id)

        conversation_history = "\n".join(
            [f"{msg.get('name', 'Unknown')}: {msg.get('content', '')}" for msg in messages]
        )

        # --- FASE 2: EXTRACCIÓN LLM (Escudo 1 - Prompting Estricto) ---
        summary_json_str = await orchestrator.run_consolidation_task(conversation_history, user_ctx)

        try:
            # --- FASE 3: PARSEO Y VALIDACIÓN ---
            clean_str = summary_json_str.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]

            extracted_facts = json.loads(clean_str.strip())

            if not isinstance(extracted_facts, list):
                logger.error(
                    "❌ El LLM no devolvió un array JSON para la sesión %s. Output: %s",
                    session_id,
                    summary_json_str,
                )

            facts_saved_for_session = 0
            for item in extracted_facts:
                fact_text = item.get("fact")
                if not fact_text:
                    continue

                try:
                    # Validamos el esquema atómico antes de hacer nada más
                    metadata = EpisodicMemoryMetadata(
                        owner_id=user_ctx.telegram_id,
                        visibility=MemoryVisibility.PRIVATE,
                        category=MemoryCategory(item.get("category", "personal_dev")),
                        type=MemoryType(item.get("type", "fact")),
                        source=MemorySource.AGENT_REFLECTION,
                        context_tags=(
                            ",".join(item.get("tags", []))
                            if isinstance(item.get("tags"), list)
                            else str(item.get("tags", ""))
                        ),
                    )

                    # --- FASE 4: DEDUPLICACIÓN SEMÁNTICA (Escudo 2 - Vector Math) ---
                    is_redundant = False
                    try:
                        # Buscamos en el archivo semántico del usuario
                        existing_memories = await memory_gateway.search_semantic_archive(
                            user_ctx=user_ctx,
                            query=fact_text,
                            limit=1,
                            domain=MemoryDomainType.EPISODIC.value,
                            # Buscamos solo en recuerdos episódicos
                        )

                        if existing_memories:
                            top_match = existing_memories[0]
                            similarity_score = top_match.score or 0.0

                            # Umbral de corte: 0.88 suele ser óptimo para cosine similarity en
                            # e5/text-embedding
                            if similarity_score > 0.88:
                                logger.info(
                                    "🔄 Recuerdo redundante omitido. Similitud: %.4f "
                                "Nuevo: '%s' | Existente: '%s'",
                                    similarity_score,
                                    fact_text,
                                    top_match.content,
                                )
                                is_redundant = True
                                total_facts_discarded += 1
                    except Exception as dedup_err:
                        # Si la búsqueda falla (ej. Qdrant timeout temporal),
                        # preferimos guardar duplicado a perder datos
                        logger.warning(
                            "⚠️ Error verificando redundancia para '%s': %s",
                            fact_text,
                            dedup_err,
                        )
                    if is_redundant:
                        continue # Saltamos la inserción y pasamos al siguiente hecho

                    # --- FASE 5: INSERCIÓN (Storage) ---
                    memory_item = EpisodicMemoryItem(
                        content=fact_text,
                        metadata=metadata,
                        created_by="system_worker"
                    )

                    await memory_gateway.save_semantic_memory(user_ctx, memory_item)
                    logger.info(
                        "💾 NUEVO Hecho guardado [%s]: %s",
                        metadata.category.value,
                        memory_item.content,
                    )
                    facts_saved_for_session += 1
                    total_facts_saved += 1

                except ValueError as ve:
                    logger.warning(
                        "⚠️ Categoría/Tipo inválido. Se descarta: %s. Razón: %s",
                        item,
                        ve,
                    )
                    continue
                except ValidationError as ve:
                    logger.warning(
                        "⚠️ Alucinación de esquema. Se descarta: %s. Razón: %s",
                        item,
                        ve,
                    )
                    continue

            # --- FASE 6: CIERRE (Mark as Consolidated) ---
            message_ids = [
                str(msg["message_id"])
                for msg in messages
                if "message_id" in msg
            ]
            await memory_gateway.mark_messages_as_consolidated(session_id, message_ids)

            processed_sessions.append(
                {
                    "session_id": session_id,
                    "messages_processed": len(messages),
                    "facts_extracted": facts_saved_for_session,
                }
            )

        except json.JSONDecodeError:
            logger.error(
                "❌ El LLM no devolvió JSON parseable para la sesión %s. Output: %s",
                session_id,
                summary_json_str,
            )

    logger.info(
        "✅ Ciclo de consolidación terminado. Guardados: %s, Descartados (Redundantes): %s",
        total_facts_saved,
        total_facts_discarded,
    )

    return {
        "status": "success",
        "facts_saved": total_facts_saved,
        "facts_discarded_as_redundant": total_facts_discarded,
        "data": processed_sessions
    }

class DeepThoughtRequest(BaseModel):
    user_id: str
    session_id: str
    user_request: str

@app.post("/system/tasks/deep_analysis", dependencies=[Depends(verify_internal_api_key)])
async def deep_analysis_task(request: DeepThoughtRequest):
    """
    Endpoint to handle complex, long-running tasks delegated by other agents.
    It's protected by an internal API key.
    """
    logger.info(f"Received deep analysis task for user {request.user_id} in session {request.session_id}")
    # Here you would add the logic to process the complex request,
    # for example, by running a CrewAI task, doing complex database queries, etc.
    # For now, we just acknowledge the reception.
    
    # This part of the code will be responsible for executing the intensive 
    # retrieval/synthesis without blocking the Fast Track webhook.
    
    return {"status": "received", "message": "Task is being processed in the background."}

class CalendarAuditRequest(BaseModel):
    user_id: str
    session_id: str
    audit_focus: str

@app.post("/system/tasks/calendar_audit", dependencies=[Depends(verify_internal_api_key)])
async def task_calendar_audit(request: CalendarAuditRequest):
    """
    Background task to perform a deep calendar audit.
    """
    logger.info(f"Received calendar audit request for user {request.user_id} with focus: {request.audit_focus}")
    
    # Stub implementation
    # In the future, this would invoke the 'schedule_analyst' agent via orchestrator.
    # orchestrator.run_background_task("schedule_analyst", task=request.audit_focus, user_id=request.user_id)
    
    return {"status": "success", "message": "Calendar audit task scheduled (STUB)"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# --- Main Entrypoint ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080")) ## All containers must listen on 8080 for cloud run
    uvicorn.run(app, host="0.0.0.0", port=port, loop="asyncio")
