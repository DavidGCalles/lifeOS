"""Configuración del edge por env. Fail-fast: sin token no hay bot."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    current_user: str
    allowed_chats: frozenset[int]
    litellm_base_url: str
    litellm_model: str
    llm_timeout: float
    llm_max_tokens: int
    poll_timeout: int
    window_size: int
    core_mcp_url: str
    memory_project: str
    llm_max_tool_rounds: int


def load_settings() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "Falta TELEGRAM_BOT_TOKEN: copia .env.example a .env y pon el "
            "token de @BotFather. El bot no arranca sin él (fail-fast)."
        )
    raw_allowed = os.environ.get("ALLOWED_CHAT_ID", "").strip()
    allowed = frozenset(
        int(x) for x in raw_allowed.replace(" ", "").split(",") if x
    )
    return Settings(
        telegram_token=token,
        current_user=os.environ.get("LIFEOS_CURRENT_USER", "David"),
        allowed_chats=allowed,
        litellm_base_url=os.environ.get(
            "LITELLM_BASE_URL", "http://litellm:4000/v1"
        ),
        litellm_model=os.environ.get("LITELLM_MODEL", "local-fallback"),
        # 300 s por defecto: un LLM local en LAN puede tardar >120 s
        # (recarga JIT del modelo tras idle) y no hay que matarle la llamada
        llm_timeout=float(os.environ.get("LLM_TIMEOUT_S", "300")),
        # cota de generación: sin max_tokens, una generación sin stop
        # puede durar minutos (E2E 16 nov: ReadTimeout a los 300 s)
        llm_max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "1024")),
        poll_timeout=int(os.environ.get("POLL_TIMEOUT", "50")),
        window_size=int(os.environ.get("WINDOW_SIZE", "5")),
        # v3-FR-02b: frontera MCP del substrato (service core-mcp del
        # compose incluido, red coreai_backend)
        core_mcp_url=os.environ.get("CORE_MCP_URL", "http://core-mcp:8000/mcp"),
        # namespace del inquilino en la unified memory (Metadata FR-3 de
        # coreAI: campo project genérico, valores del inquilino)
        memory_project=os.environ.get("LIFEOS_MEMORY_PROJECT", "lifeos"),
        # rondas máx de tool loop por mensaje: cada ronda es un pase del
        # LLM (razonamiento incluido) — bounded por diseño, no infinito
        llm_max_tool_rounds=int(os.environ.get("LLM_MAX_TOOL_ROUNDS", "3")),
    )
