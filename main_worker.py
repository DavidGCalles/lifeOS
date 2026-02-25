import os
import logging
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from typing import Optional
import asyncio

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
        # Determine the user context from the first message
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

        # Run consolidation crew
        summary = await orchestrator.run_consolidation_crew(conversation_history, user_ctx)

        # Create episodic memory item
        memory_item = EpisodicMemoryItem(
            content=summary,
            metadata=EpisodicMemoryMetadata(
                owner_id=user_ctx.telegram_id,
                domain=MemoryDomainType.EPISODIC,
                visibility=MemoryVisibility.PRIVATE,
                original_session_id=session_id,
                category=MemoryCategory.META,
                type=MemoryType.REFLECTION,
                source=MemorySource.USER_CHAT,
            )
        )

        # Save to vector store
        memory_id = "placeholder_memory_id"  # Replace with actual ID returned from save_semantic_memory
        #memory_id = await memory_gateway.save_semantic_memory(user_ctx, memory_item)
        total_facts_saved += 1

        # Mark messages as consolidated
        message_ids = [str(msg["message_id"]) for msg in messages if "message_id" in msg]
        #await memory_gateway.mark_messages_as_consolidated(session_id, message_ids)

        processed_sessions.append({
            "session_id": session_id,
            "messages_processed": len(messages),
            "summary": summary,
            "memory_id": memory_id
        })

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
