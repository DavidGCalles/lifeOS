import logging
import asyncio
from typing import Any
from telegram import Update
from src.sensory.base_driver import SensoryDriver, SensoryType

logger = logging.getLogger(__name__)

class SensoryCortex:
    """
    Middleware central que enruta los inputs no textuales al driver adecuado.
    """
    _instance: "SensoryCortex | None" = None
    _drivers: dict[str, SensoryDriver] = {}

    def __new__(cls) -> "SensoryCortex":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            logger.info("🧠 Sensory Cortex Online: Initialized.")
        return cls._instance

    @classmethod
    def get_instance(cls) -> "SensoryCortex":
        """Alternative singleton access."""
        return cls()

    def register_driver(self, telegram_field: str, driver: SensoryDriver) -> None:
        """
        Vincula un campo de Telegram con un Driver específico.
        Ej: register_driver('photo', VisualDriver())
        """
        self._drivers[telegram_field] = driver
        logger.info(f"   👁️  Sense Registered: [{telegram_field}] -> {driver.__class__.__name__} ({driver.sensory_type.value})")

    async def run_forever(self) -> None:
        """
        Keep the cortex alive if background tasks are needed.
        Currently just waits for cancellation.
        """
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Sensory Cortex background task cancelled.")

    async def process(self, update: Update) -> dict[str, Any] | None:
        """
        Inspecciona el update y delega al driver correcto si existe.
        """
        if not update.message:
            return None

        # Iteramos sobre los triggers registrados
        for field, driver in self._drivers.items():
            # Check de existencia (Pythonic truthy check)
            if getattr(update.message, field, None):
                # Logging robusto usando el Enum
                logger.info(f"🧠 Sensory Cortex: Signal detected on '{field}'. Routing to {driver.sensory_type.name} driver...")
                
                try:
                    return await driver.process(update)
                except Exception as e:
                    logger.error(f"❌ Sensory Cortex Error ({driver.sensory_type.name}): {e}", exc_info=True)
                    return None
        
        return None