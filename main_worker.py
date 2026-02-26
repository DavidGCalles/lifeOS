import os
import logging
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from typing import Optional
import asyncio
import json
from pydantic import ValidationError

from src.memory_gateway import MemoryGateway
from src.crew_orchestrator import CrewOrchestrator
from src.schemas.memory import EpisodicMemoryItem, EpisodicMemoryMetadata, MemoryDomainType, MemoryVisibility, MemoryCategory, MemoryType, MemorySource
from src.identity_manager import IdentityManager, UserContext, UserRole


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
SYSTEM_CRON_TOKEN = os.getenv("SYSTEM_CRON_TOKEN")
if not SYSTEM_CRON_TOKEN:
    logger.warning("SYSTEM_CRON_TOKEN is not set. Worker endpoints will be insecure.")

# --- Globals ---
memory_gateway = MemoryGateway()
orchestrator = CrewOrchestrator(memory_gateway=memory_gateway)


# --- FastAPI App ---
app = FastAPI()

# --- Security Dependency ---
async def verify_cron_token(request: Request):
    """Dependency to verify the cron token."""
    if not SYSTEM_CRON_TOKEN:
        # Allow access if the token is not set, but log a warning.
        # This is for local development convenience. In production, the token should always be set.
        logger.warning("Allowing request to worker endpoint without token verification.")
        return
    
    token = request.headers.get("X-Cron-Token")
    if token != SYSTEM_CRON_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing cron token")

# --- Worker Endpoints ---
@app.post("/system/cron/consolidate", dependencies=[Depends(verify_cron_token)])
async def consolidate_memory():
    """
    Endpoint to trigger memory consolidation.
    """
    logger.info("Received request to consolidate memory.")
    
    unconsolidated_sessions = await memory_gateway.fetch_unconsolidated_sessions()
    
    if not unconsolidated_sessions:
        return {"status": "success", "message": "No unconsolidated memories found."}

    total_facts_saved = 0
    processed_sessions = []

    for session_id, messages in unconsolidated_sessions.items():
        if not messages:
            continue
        
        owner_id = messages[0].get("metadata", {}).get("owner_id")
        if not owner_id:
            logger.warning(f"Skipping session {session_id} due to missing owner_id in the first message.")
            continue

        user_ctx = await IdentityManager.get_user(owner_id)

        # Format conversation history
        conversation_history = "\n".join(
            [f"{msg.get('name', 'Unknown')}: {msg.get('content', '')}" for msg in messages]
        )

        # Run consolidation task using FastTrack
        summary_json_str = await orchestrator.run_consolidation_task(conversation_history, user_ctx)

        try:
            # Limpieza brutal del output del LLM
            clean_str = summary_json_str.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]
                
            extracted_facts = json.loads(clean_str.strip())
            
            if not isinstance(extracted_facts, list):
                logger.error(f"❌ El LLM no devolvió un array JSON para la sesión {session_id}. Output: {summary_json_str}")
                continue # Saltamos esta sesión y no la marcamos como consolidada

            facts_saved_for_session = 0
            for item in extracted_facts:
                try:
                    metadata = EpisodicMemoryMetadata(
                        owner_id=user_ctx.telegram_id,
                        visibility=MemoryVisibility.PRIVATE,
                        category=MemoryCategory(item.get("category", "personal_dev")),
                        type=MemoryType(item.get("type", "fact")),
                        source=MemorySource.AGENT_REFLECTION,
                        context_tags=",".join(item.get("tags", [])) if isinstance(item.get("tags"), list) else str(item.get("tags", ""))
                    )

                    memory_item = EpisodicMemoryItem(
                        content=item.get("fact"),
                        metadata=metadata,
                        created_by="system_worker"
                    )

                    # Llamada real a base de datos
                    #await memory_gateway.save_semantic_memory(user_ctx, memory_item)
                    logger.info(f"💾 Hecho guardado [{metadata.category.value}]: {memory_item.content}")
                    facts_saved_for_session += 1
                    total_facts_saved += 1

                except ValueError as ve:
                    # Captura fallos al instanciar los Enums si el LLM se inventa la categoría/tipo
                    logger.warning(f"⚠️ Categoría/Tipo inválido detectado. Se descarta este hecho: {item}. Razón: {ve}")
                    continue
                except ValidationError as ve:
                    # Captura fallos de estructura de Pydantic
                    logger.warning(f"⚠️ Alucinación de esquema detectada. Se descarta este hecho: {item}. Razón: {ve}")
                    continue

            # Marcar mensajes como consolidados SOLO si el JSON base era válido
            message_ids = [str(msg["message_id"]) for msg in messages if "message_id" in msg]
            #await memory_gateway.mark_messages_as_consolidated(session_id, message_ids)

            processed_sessions.append({
                "session_id": session_id,
                "messages_processed": len(messages),
                "facts_extracted": facts_saved_for_session
            })

        except json.JSONDecodeError:
            logger.error(f"❌ El LLM no devolvió JSON parseable para la sesión {session_id}. Output: {summary_json_str}")
            # NO marcamos como consolidado para que el worker lo reintente en el próximo ciclo

    return {
        "status": "success",
        "facts_saved": total_facts_saved,
        "data": processed_sessions
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

# --- Main Entrypoint ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080")) ## All containers must listen on 8080 for cloud run
    uvicorn.run(app, host="0.0.0.0", port=port, loop="asyncio")
