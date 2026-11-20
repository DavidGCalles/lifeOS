"""edge-bot — v3-FR-02a + v3-FR-02b: loop E2E con memoria vía dispatch.

Telegram 1:1 → persona por defecto (Jane) → LLM vía gateway de coreAI
(litellm) → respuesta al chat. Desde v3-FR-02b (#169) Jane tiene DOS
tools de borde (memory_save / memory_recall) que se traducen a los
contratos del substrato por MCP (core-mcp, streamable HTTP): guardar es
un dispatch (write-then-read: el dispatch aceptado es el acuse), y
recuperar es el recall síncrono read-only. El edge NO persiste memoria
propia: la ventana efímera es contexto conversacional, la persistencia
es solo la de coreAI.
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
from .mcp import CoreMCPClient
from .memory_tools import EDGE_TOOLS, MemoryTools
from .personas import default_persona, load_personas, render_system_prompt
from .telegram import TelegramClient, TelegramError
from .transport import PollingTransport

logging.basicConfig(
    level=logging.INFO,
    format="%asctime%s %name%s %levelname%s %message%s",
)
# httpx loguea a INFO la URL completa de CADA petición, y la URL del bot de
# Telegram lleva el token en claro: log pegado = token quemado (E2E 16 nov:
# el token salió en cada línea de httpx). Sus líneas INFO no aportan nada
# que no logueemos ya por nuestra cuenta: a WARNING solo salen los errores,
# y el token desaparece del log.
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("edge-bot")

# fail-fast en el arranque: sin token no hay bot
settings = load_settings()
personas = load_personas()
persona = default_persona(personas)
system_prompt = render_system_prompt(persona, settings.current_user)

# módulos aislados y swapeables: la ventana efímera es CONTEXTO
# conversacional, no almacenamiento (la persistencia es del substrato)
memory = EphemeralMemory(settings.window_size)
telegram = TelegramClient(settings.telegram_token)
llm = GatewayLLM(
    settings.litellm_base_url, settings.litellm_model,
    timeout=settings.llm_timeout,
    max_tokens=settings.llm_max_tokens,
)
transport = PollingTransport(telegram, settings.poll_timeout)
# v3-FR-02b: canal al substrato + superficie de 2 tools para la persona
substrate = CoreMCPClient(settings.core_mcp_url)
memory_tools = MemoryTools(substrate, settings.memory_project)


async def respond(chat_id: int, text: str, task: str) -> tuple[str, bool]:
    """LLM + loop de function calling bounded. Devuelve (respuesta, limpia).

    limpia=False → alguna tool falló: el turno NO se registra en la ventana
    efímera (diseño del #169: una tool rota no deja "hecho" conversacional).
    Los fallos de tool NO lanzan: llegan al modelo como resultado de tool
    y Jane los comunica; el loop del bot nunca muere por una tool (02a).
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages += memory.history(chat_id)
    messages.append({"role": "user", "content": text})

    clean = True
    rounds = 0
    while True:
        # cupo de rondas: el tools param se retira al agotarse, forzando al
        # modelo a responder con texto (un bucle de tool_calls infinito con
        # un modelo de razonamiento local sería minutos por mensaje)
        allow_tools = rounds < settings.llm_max_tool_rounds
        msg = await llm.chat(
            messages, tools=EDGE_TOOLS if allow_tools else None
        )
        calls = [
            c for c in (msg.get("tool_calls") or [])
            if (c.get("type") or "function") == "function"
        ]
        if not calls:
            break
        if not allow_tools:
            log.warning(
                "task=%s el modelo insiste en tools con el cupo agotado; "
                "corto sin ejecutar más", task,
            )
            break
        rounds += 1
        # eco canónico del assistant con tool_calls (solo las claves del
        # contrato chat: content/tools sin campos extra del modelo)
        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": msg["tool_calls"],
        })
        for call in calls:
            ok, result = await memory_tools.execute(call, task)
            if not ok:
                clean = False
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id") or "",
                "content": result,
            })
    return (msg.get("content") or "").strip(), clean


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

    try:
        reply, clean = await respond(chat_id, text, task)
    except LLMError as e:
        log.error("task=%s fallo LLM: %s", task, e)
        await telegram.send_message(
            chat_id,
            "Me ha fallado el motor (gateway de coreAI). "
            "Vuelve a intentarlo en un momento.",
        )
        return

    if not reply:
        # finish degenerado puede devolver contenido vacío: sin turno en
        # memoria (no hubo respuesta real) y el usuario sabe qué pasó
        log.warning("task=%s respuesta vacía del LLM, turno no registrado", task)
        await telegram.send_message(
            chat_id,
            "El motor ha devuelto una respuesta vacía. Vuelve a intentarlo.",
        )
        return

    if not clean:
        # alguna tool falló: la respuesta de Jane (que avisa del fallo de
        # memoria) se entrega, pero el turno no se registra — un fallo de
        # memoria no deja huella conversacional "hecha" (diseño del #169)
        log.warning("task=%s turno con fallo de tool: no se registra", task)
    else:
        # la ventana solo registra turnos completos: si el LLM falla, nada
        memory.append(chat_id, {"role": "user", "content": text})
        memory.append(chat_id, {"role": "assistant", "content": reply})
    try:
        await telegram.send_message(chat_id, reply)
    except TelegramError as e:
        # el turno queda en memoria (la conversación siguió su curso
        # aunque la entrega fallara): un fallo de envío no mata el loop
        log.error("task=%s fallo al enviar a Telegram: %s", task, e)
        return
    log.info("task=%s out ok reply=%r", task, reply[:120])


async def bot_loop() -> None:
    log.info(
        "edge-bot arriba: persona=%r usuario=%r modelo=%r ventana=%d "
        "timeout_llm=%.0fs max_tokens=%d core_mcp=%r project=%r rondas_tools=%d",
        persona.get("role"), settings.current_user,
        settings.litellm_model, settings.window_size,
        settings.llm_timeout, settings.llm_max_tokens,
        settings.core_mcp_url, settings.memory_project,
        settings.llm_max_tool_rounds,
    )
    try:
        async for update in transport.updates():
            # INVULNERABLE A NIVEL DE UPDATE: el E2E 16 nov lo mató un 400
            # de sendMessage (mensaje >4096 chars) sin capturar — el bot
            # quedaba mudo con healthcheck verde. Ninguna excepción de una
            # update puede tumbar el loop: se loguea y se sigue con la
            # siguiente.
            try:
                await handle(update)
            except Exception:
                log.exception("update con excepción no capturada; el loop sigue")
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
