"""LLM vía el gateway de coreAI (litellm). El edge jamás llama modelos
directamente: todo el tráfico pasa por el gateway (observabilidad, fallback)."""
import logging
import time

import httpx

log = logging.getLogger("edge-bot.llm")


class LLMError(RuntimeError):
    pass


class GatewayLLM:
    def __init__(self, base_url: str, model: str, timeout: float = 300.0,
                 max_tokens: int = 1024):
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=5.0)
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def chat(self, messages: list[dict]) -> str:
        t0 = time.monotonic()
        body = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.4,
            # cota de generación: sin max_tokens una generación sin stop
            # puede durar minutos y el cliente se come el timeout entero
            "max_tokens": self._max_tokens,
        }
        try:
            resp = await self._client.post(self._url, json=body)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            # duración siempre: la latencia del loop la pone el LLM, y así
            # la vemos sin cronómetro (ReadTimeout str vacío no nos tapa nada)
            log.info("llm %s ok en %.1f s", self._model, time.monotonic() - t0)
            return content
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            # type(e).__name__ SIEMPRE: ReadTimeout/ConnectTimeout serializan
            # a string vacío y el error quedaba mudito ("fallo LLM: ...: ")
            raise LLMError(
                f"gateway {self._model} tras {time.monotonic() - t0:.1f} s: "
                f"{type(e).__name__}: {e}"
            ) from e
