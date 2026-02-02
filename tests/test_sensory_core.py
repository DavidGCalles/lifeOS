import unittest
from unittest.mock import MagicMock
from typing import Any
from telegram import Update, Message
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sensory.cortex import SensoryCortex
from src.sensory.base_driver import SensoryDriver, SensoryType
# --- MOCK DRIVER ---
class GhostDriver(SensoryDriver):
    """Driver falso para pruebas."""
    
    @property
    def sensory_type(self) -> SensoryType:
        return SensoryType.DEBUG  # <--- Uso estricto del Enum

    async def process(self, update: Update) -> dict[str, Any] | None:
        return {
            "role": "user",
            "content": [{"type": "text", "text": "BOO!"}]
        }

class TestSensoryCortex(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        SensoryCortex._instance = None
        SensoryCortex._drivers = {} 
        self.cortex = SensoryCortex()
        
    async def test_routing(self):
        print("\n>>> 🧪 TEST: Sensory Cortex Routing (Strict Enums)")
        
        # 1. Registrar
        driver = GhostDriver()
        self.cortex.register_driver('animation', driver)
        
        # 2. Mockear Update
        mock_update = MagicMock(spec=Update)
        mock_message = MagicMock(spec=Message)
        
        # Simulamos que llega una animación (GIF)
        mock_message.animation = True   
        mock_message.photo = None      
        
        mock_update.message = mock_message

        # 3. Procesar
        result = await self.cortex.process(mock_update)

        # 4. Verificar
        self.assertIsNotNone(result)
        if result:
            self.assertEqual(result['content'][0]['text'], "BOO!")
        
        print(f"   ✅ Routing Successful via {driver.sensory_type.name}")

if __name__ == '__main__':
    unittest.main()