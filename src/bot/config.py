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
    poll_timeout: int
    window_size: int


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
        poll_timeout=int(os.environ.get("POLL_TIMEOUT", "50")),
        window_size=int(os.environ.get("WINDOW_SIZE", "5")),
    )
