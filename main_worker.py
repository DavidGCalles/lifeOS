import os
import logging
from fastapi import FastAPI, Request, Response, Depends, HTTPException
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
SYSTEM_CRON_TOKEN = os.getenv("SYSTEM_CRON_TOKEN")
if not SYSTEM_CRON_TOKEN:
    logger.warning("SYSTEM_CRON_TOKEN is not set. Worker endpoints will be insecure.")

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
    This is a placeholder for the actual consolidation logic.
    """
    logger.info("Received request to consolidate memory.")
    # Here you would typically trigger a background task for consolidation.
    # For now, we'll just return a success message.
    return {"status": "success", "message": "Memory consolidation triggered."}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

# --- Main Entrypoint ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080")) ## All containers must listen on 8080 for cloud run
    uvicorn.run(app, host="0.0.0.0", port=port, loop="asyncio")
