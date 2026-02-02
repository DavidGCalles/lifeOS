import unittest
import io
import base64
from unittest.mock import MagicMock, AsyncMock
from PIL import Image
from telegram import Update, Message, PhotoSize, Bot, File
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sensory.drivers.visual_driver import VisualDriver
from src.sensory.base_driver import SensoryType

class TestVisualDriver(unittest.IsolatedAsyncioTestCase):
    
    def _create_dummy_image(self, width=2000, height=2000, color='red') -> io.BytesIO:
        """Crea una imagen válida en memoria para testear el resize."""
        img = Image.new('RGB', (width, height), color=color)
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        buf.seek(0)
        return buf

    async def test_process_flow_with_resize(self):
        print("\n>>> 🧪 TEST: Visual Driver (Download + Resize + Base64)")
        
        # 1. SETUP: Crear Driver
        driver = VisualDriver()
        self.assertEqual(driver.sensory_type, SensoryType.VISUAL)

        # 2. SETUP: Mocks de Telegram
        # Necesitamos simular: Update -> Message -> Photo -> Bot -> File -> download
        
        # A. La imagen falsa (Grande para forzar resize)
        original_img_buffer = self._create_dummy_image(2000, 2000)
        
        # B. El objeto File de Telegram (el que tiene el método download_to_memory)
        mock_file = MagicMock(spec=File)
        # download_to_memory es una corrutina que escribe en el buffer que le pasas
        async def mock_download(out):
            out.write(original_img_buffer.getvalue())
            return None
        mock_file.download_to_memory = AsyncMock(side_effect=mock_download)
        
        # C. El Bot (el que tiene get_file)
        mock_bot = MagicMock(spec=Bot)
        mock_bot.get_file = AsyncMock(return_value=mock_file)

        # D. El Update y el Mensaje
        mock_update = MagicMock(spec=Update)
        mock_message = MagicMock(spec=Message)
        mock_photo = MagicMock(spec=PhotoSize)
        
        mock_photo.file_id = "fake_file_id_123"
        mock_photo.width = 2000
        mock_photo.height = 2000
        
        mock_message.photo = [mock_photo] # Lista de fotos
        mock_message.caption = "Look at this red square"
        mock_update.message = mock_message
        
        # Inyectamos el bot en el update (así funciona update.get_bot())
        mock_update.get_bot.return_value = mock_bot

        # 3. EJECUCIÓN
        payload = await driver.process(mock_update)

        # 4. ASERCIONES
        self.assertIsNotNone(payload)
        content = payload["content"]
        
        # Verificar Estructura
        self.assertEqual(len(content), 2)
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[0]["text"], "Look at this red square")
        
        self.assertEqual(content[1]["type"], "image_url")
        base64_url = content[1]["image_url"]["url"]
        self.assertTrue(base64_url.startswith("data:image/jpeg;base64,"))
        
        # Verificar que el Resize funcionó
        # Decodificamos el base64 resultante para ver sus dimensiones reales
        base64_data = base64_url.split(",")[1]
        decoded_img_data = base64.b64decode(base64_data)
        with Image.open(io.BytesIO(decoded_img_data)) as result_img:
            w, h = result_img.size
            print(f"   📏 Original: 2000x2000 | Result: {w}x{h}")
            self.assertLessEqual(w, 1024)
            self.assertLessEqual(h, 1024)
        
        print("   ✅ Visual Driver processed and optimized image correctly.")

    async def test_no_photo(self):
        """Verifica que devuelve None si no hay foto."""
        driver = VisualDriver()
        mock_update = MagicMock(spec=Update)
        mock_update.message.photo = [] # Lista vacía
        
        result = await driver.process(mock_update)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()