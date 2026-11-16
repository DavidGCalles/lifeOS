"""edge-bot — v3-FR-02a: loop mínimo E2E.

Telegram 1:1 → persona por defecto (Jane) → LLM vía gateway de coreAI
(litellm) → respuesta al chat. Sin tools, sin memoria persistente.
Trazabilidad: cada update se procesa bajo un task-UUID presente en todas
las líneas de log (convención del stack desde el commit uno).
"""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import load_settings
from .ephemeral_memory import EphemeralMemory
from .llm import GatewayLLM, LLMError
from .personas import default_persona, load_personas, render_system_prompt
from .telegram import TelegramClient
from .transport import PollingTransport

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("edge-bot")

# fail-fast en el arranque: sin token no hay bot
settings = load_settings()
personas = load_personas()
persona = default_persona(personas)
system_prompt = render_system_prompt(persona, settings.current_user)

# módulos aislados y swapeables: memoria efímera (FR-02b la sustituirá)
memory = EphemeralMemory(settings.window_size)
telegram = TelegramClient(settings.telegram_token)
llm = GatewayLLM(
    settings.litellm_base_url, settings.litellm_model,
    timeout=settings.llm_timeout,
)
transport = PollingTransport(telegram, settings.poll_timeout)


async def handle(update: dict) -> None:
    task = uuid.uuid4().hex[:8]
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        log.info("task=%s update sin texto (1:1), ignorado", task)
        return
    if chat.get("type") != "private":
        # v3-FR-02a es 1:1; grupos y Social Shield llegan en v3-FR-05
        log.info("task=%s chat=%s no es privado, fuera de v3-FR-02a", task, chat_id)
        return
    if settings.allowed_chats and chat_id not in settings.allowed_chats:
        log.warning("task=%s chat=%s fuera de whitelist, ignorado", task, chat_id)
        return

    log.info("task=%s in chat=%s text=%r", task, chat_id, text[:120])

    messages = [{"role": "system", "content": system_prompt}]
    messages += memory.history(chat_id)
    messages.append({"role": "user", "content": text})

    try:
        reply = await llm.chat(messages)
    except LLMError as e:
        log.error("task=%s fallo LLM: %s", task, e)
        await telegram.send_message(
            chat_id,
            "Me ha fallado el motor (gateway de coreAI). "
            "Vuelve a intentarlo en un momento.",
        )
        return

    # la ventana solo registra turnos completos: si el LLM falla, nada
    memory.append(chat_id, {"role": "user", "content": text})
    memory.append(chat_id, {"role": "assistant", "content": reply})
    await telegram.send_message(chat_id, reply)
    log.info("task=%s out ok reply=%r", task, reply[:120])


async def bot_loop() -> None:
    log.info(
        "edge-bot arriba: persona=%r usuario=%r modelo=%r ventana=%d timeout_llm=%.0fs",
        persona.get("role"), settings.current_user,
        settings.litellm_model, settings.window_size, settings.llm_timeout,
    )
    try:
        async for update in transport.updates():
            await handle(update)
    finally:
        await telegram.close()
        await llm.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(bot_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="LifeOS edge-bot", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "persona": persona.get("role"),
        "user": settings.current_user,
    }
