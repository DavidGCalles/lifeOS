"""Módulo de memoria efímera — v3-FR-02a.

Rolling window de los últimos WINDOW_SIZE mensajes por chat, en RAM.
AISLADO A PROPÓSITO [DAVID]: este módulo se desactiva o se swapea (p. ej.
por la memoria vía dispatch de v3-FR-02b) sin tocar el resto del bot.
Muere con el contenedor: el edge no persiste nada propio (DoD v3-FR-02a).

INVARIANTE de forma: la ventana SIEMPRE empieza en un turno completo
(user primero). El recorte no puede dejar un assistant huérfano al frente:
los templates de chat de los modelos no lo toleran (LM Studio: jinja
"No user query found in messages" → 400; E2E 16 nov, dos veces).
"""
from collections import OrderedDict


class EphemeralMemory:
    """Ventana deslizante por chat_id. Sin disco, sin DB, sin recuperación."""

    def __init__(self, window_size: int = 5):
        self._size = max(1, window_size)
        self._store: OrderedDict[int, list[dict]] = OrderedDict()

    def history(self, chat_id: int) -> list[dict]:
        return list(self._store.get(chat_id, []))

    def append(self, chat_id: int, message: dict) -> None:
        window = self._store.setdefault(chat_id, [])
        window.append(message)
        del window[:-self._size]
        # turno huérfano al frente: el recorte de ventana impar partió un
        # par user/assistant — se cae el resto del par para conservar la
        # alternancia clásica que los templates de chat esperan
        if window and window[0].get("role") == "assistant":
            del window[0]
        # LRU de chats: si un día hace falta acotar, aquí está el gancho
        self._store.move_to_end(chat_id)

    def forget(self, chat_id: int) -> None:
        self._store.pop(chat_id, None)
