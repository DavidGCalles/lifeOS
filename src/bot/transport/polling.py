"""Long polling (getUpdates) — el transporte on-prem: sin URL pública, sin TLS.

Con timeout largo (50 s) Telegram responde EN CUANTO llega el update: la
latencia extra frente a un webhook es solo el reconnect TLS (~100-300 ms).
REGLAS DURAS aprendidas del legacy:
- Un SOLO poller por token: dos getUpdates concurrentes → 409 Conflict.
- Si quedó un setWebhook activo, getUpdates falla hasta deleteWebhook.
- El offset avanza ANTES de procesar (un crash no reprocesa lo ya visto).
"""
import asyncio
import logging

from ..telegram import TelegramClient, TelegramError

log = logging.getLogger("edge-bot.transport")


class PollingTransport:
    def __init__(self, client: TelegramClient, poll_timeout: int = 50):
        self._client = client
        self._timeout = poll_timeout
        self._offset: int | None = None

    async def updates(self):
        while True:
            try:
                batch = await self._client.get_updates(self._offset, self._timeout)
            except TelegramError as e:
                # 409 (doble poller / webhook residuo) y similares: backoff,
                # que el ruido no dispare un spin-loop
                log.warning("getUpdates rechazado (%s); backoff 10 s", e)
                await asyncio.sleep(10)
                continue
            for update in batch:
                self._offset = update["update_id"] + 1
                yield update
