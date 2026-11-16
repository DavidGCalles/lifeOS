"""Interfaz de transporte de updates de Telegram.

v3-FR-02a implementa PollingTransport. Un WebhookTransport futuro (endpoint
FastAPI del propio servicio) sería el swap si el edge vive algún día en un
host con endpoint público: mismo contrato, el bot no se entera.
"""
from typing import AsyncIterator, Protocol


class Transport(Protocol):
    def updates(self) -> AsyncIterator[dict]:
        """Itera infinitamente sobre los updates entrantes."""
        ...
