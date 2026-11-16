"""LLM vía el gateway de coreAI (litellm). El edge jamás llama modelos
directamente: todo el tráfico pasa por el gateway (observabilidad, fallback)."""
import logging

import httpx

log = logging.getLogger("edge-bot.llm")


class LLMError(RuntimeError):
    pass


class GatewayLLM:
    def __init__(self, base_url: str, model: str):
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=5.0)
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def chat(self, messages: list[dict]) -> str:
        try:
            resp = await self._client.post(
                self._url,
                json={"model": self._model, "messages": messages,
                      "temperature": 0.4},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise LLMError(f"gateway {self._model}: {e}") from e
