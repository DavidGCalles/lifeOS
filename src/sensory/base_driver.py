from abc import ABC, abstractmethod
from enum import StrEnum, auto
from typing import Any
from telegram import Update

class SensoryType(StrEnum):
    """
    Catálogo estricto de los sentidos disponibles en LifeOS.
    """
    VISUAL = auto()   # Fotos, Imágenes comprimidas
    AUDIO = auto()    # Notas de voz, Archivos de audio
    DOCUMENT = auto() # Documentos (PDF, Texto)
    VIDEO = auto()    # Video notas (Future Scope)
    LOCATION = auto() # GPS (Future Scope)
    DEBUG = auto()    # Para tests internos

class SensoryDriver(ABC):
    """
    Clase abstracta que define el contrato para todos los módulos sensoriales.
    """

    @property
    @abstractmethod
    def sensory_type(self) -> SensoryType:
        """Devuelve el tipo de sentido de este driver."""
        pass

    @abstractmethod
    async def process(self, update: Update) -> dict[str, Any] | None:
        """
        Procesa asíncronamente un Update.
        
        Returns:
            dict[str, Any]: Payload OpenAI Multimodal estándar.
            None: Si el driver no puede procesar el mensaje.
        """
        pass