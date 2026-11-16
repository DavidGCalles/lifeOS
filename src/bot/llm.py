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
            # EL CUERPO DEL ERROR ES EL DIAGNÓSTICO: litellm/LM Studio dicen
            # ahí la razón literal del rechazo. raise_for_status solo dice
            # "400" y tira el cuerpo a la basura (dos ciegos comprados).
            if resp.status_code >= 400:
                raise LLMError(
                    f"gateway {self._model} tras {time.monotonic() - t0:.1f} s: "
                    f"HTTP {resp.status_code}: {resp.text[:500]}"
                )
            data = resp.json()
            choice = data["choices"][0]
            content = (choice.get("message") or {}).get("content", "").strip()
            usage = data.get("usage") or {}
            if not content:
                # DIAGNÓSTICO de la respuesta vacía (E2E 16 nov, dos
                # casos con la misma firma: finish='length' tokens_out=1024
                # y content vacío). ¿Se fue el texto a reasoning_content
                # (modelo de razonamiento que se gasta el techo pensando)
                # o fue un loop degenerado de whitespace? El choice crudo
                # lo dice. Solo se loguea en el caso vacío: cero ruido
                # en el flujo normal.
                msg = choice.get("message") or {}
                log.warning(
                    "contenido vacío: finish=%r content=%r reasoning=%r "
                    "msg_keys=%s usage=%s",
                    choice.get("finish_reason"),
                    (msg.get("content") or "")[:300],
                    (msg.get("reasoning_content") or "")[:300],
                    sorted(msg.keys()), usage,
                )
            # finish_reason y tokens de salida: si Jane vuelve a salir
            # decapitada ("stop" degenerado vs "length"), aquí se ve
            log.info(
                "llm %s ok en %.1f s finish=%r tokens_out=%s",
                self._model, time.monotonic() - t0,
                choice.get("finish_reason"), usage.get("completion_tokens"),
            )
            return content
        except LLMError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            # type(e).__name__ SIEMPRE: ReadTimeout/ConnectTimeout serializan
            # a string vacío y el error quedaba mudito ("fallo LLM: ...: ")
            raise LLMError(
                f"gateway {self._model} tras {time.monotonic() - t0:.1f} s: "
                f"{type(e).__name__}: {e}"
            ) from e
