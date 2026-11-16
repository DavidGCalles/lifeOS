"""Capa de API de Telegram: solo lo que v3-FR-02a necesita."""
import asyncio
import logging

import httpx

log = logging.getLogger("edge-bot.telegram")


class TelegramError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str, timeout: float = 60.0):
        self._api = f"https://api.telegram.org/bot{token}"
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def _call(self, method: str, payload: dict) -> dict:
        resp = await self._client.post(f"{self._api}/{method}", json=payload)
        data = resp.json()
        if not data.get("ok"):
            raise TelegramError(
                f"{method}: HTTP {resp.status_code} — {data.get('description', '?')}"
            )
        return data["result"]

    async def get_updates(self, offset: int | None, timeout: int) -> list[dict]:
        """Long polling: la conexión queda abierta hasta que llega un update
        o expira `timeout`. NO es sondeo corto: la latencia es la de push.
        Solo 'message' (v3-FR-02a); los grupos llegan con v3-FR-05."""
        try:
            return await self._call(
                "getUpdates",
                {"offset": offset, "timeout": timeout,
                 "allowed_updates": ["message"]},
            )
        except httpx.ReadTimeout:
            return []  # expiración limpia del long poll: no es error
        except (httpx.ReadError, httpx.ConnectError) as e:
            log.warning("getUpdates: error de transporte (%s); backoff 5 s", e)
            await asyncio.sleep(5)
            return []

    async def send_message(self, chat_id: int, text: str) -> None:
        await self._call("sendMessage", {"chat_id": chat_id, "text": text})
