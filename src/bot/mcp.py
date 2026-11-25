"""Cliente MCP del substrato (core-mcp) — v3-FR-02b (#169).

El edge habla con la unified memory de coreAI EXCLUSIVAMENTE por aquí:
streamable HTTP contra el service `core-mcp :8000` (ADR-008 del substrato,
su transporte principal; STDIO quedó interino). SDK pin `mcp==2.1.1` —
paridad exacta con el substrato, mismo patrón de cliente que sus propios
tests ejercitan contra el wire.

SESIÓN POR LLAMADA: connect → initialize → call_tool → close, por cada
tool call. Sin sesión persistente que gestionar: cada llamada trae su
canal propio, el cliente es inmune a reinicios de core-mcp (la siguiente
llamada reconecta sola) y el coste extra en red local es un handshake de
milisegundos. La alternativa (sesión larga respawneable) es complejidad
de re-conexión que v1 no necesita.

DoD del issue: el edge NO persiste memoria propia — este módulo no toca
disco ni DB; todo pasa por el substrato via dispatch.
"""
import logging

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

log = logging.getLogger("edge-bot.mcp")


class SubstrateError(RuntimeError):
    """Fallo hablando con core-mcp: transporte caído, isError del substrato
    o respuesta con forma inesperada. El loop del bot NO muere por esto:
    la tool la traduce en un aviso de Jane, no en excepción."""


def _is_error(result) -> bool:
    """Atributo de error snake/camel-agnóstico (línea v2 del SDK)."""
    return bool(getattr(result, "is_error", getattr(result, "isError", False)))


def _join_text(result) -> str:
    """Concatena los bloques de texto del resultado (frontera del substrato:
    contesta en un único bloque de texto serializado)."""
    parts = []
    for item in getattr(result, "content", None) or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


class CoreMCPClient:
    """Canal del edge hacia core-mcp. Una instancia, muchas llamadas
    puntuales; el state vive solo dentro de cada call."""

    def __init__(self, url: str):
        self._url = url

    async def call(self, name: str, arguments: dict, task: str = "-") -> str:
        """Ejecuta UNA tool del substrato y devuelve su texto de respuesta.

        Raises:
            SubstrateError: transporte, isError del substrato o respuesta
                sin contenido. Traza honesta {Clase}: {mensaje}.
        """
        try:
            async with streamable_http_client(self._url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
        except Exception as e:
            # type(e).__name__ SIEMPRE: los errores del SDK transportan
            # mensaje legible, pero ya nos pasó con ReadTimeout que una
            # excepción serializa a string vacío y el error queda mudito
            # (lección del 02a) — la clase SIEMPRE dice algo
            raise SubstrateError(
                f"core-mcp {name} task={task}: {type(e).__name__}: {e}"
            ) from e
        text = _join_text(result)
        if _is_error(result):
            # isError: el substrato ya dijo QUÉ falló en su texto literal
            # (validación de contrato, colección ausente...): se entrega,
            # no se envuelve en un diagnóstico genérico
            raise SubstrateError(
                f"core-mcp {name} task={task} respondió con error: "
                f"{text[:300] or 'sin texto de diagnóstico'}"
            )
        if not text:
            raise SubstrateError(
                f"core-mcp {name} task={task} respondió sin contenido"
            )
        log.info("mcp %s task=%s ok (%d chars)", name, task, len(text))
        return text
