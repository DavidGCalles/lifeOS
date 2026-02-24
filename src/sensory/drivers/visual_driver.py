import io
import base64
import logging
import time
from typing import Any
from PIL import Image
from telegram import Update
from src.sensory.base_driver import SensoryDriver, SensoryType

logger = logging.getLogger(__name__)

class VisualDriver(SensoryDriver):
    """
    Driver encargado de procesar imágenes estáticas (PhotoSize).
    Descarga, optimiza (resize) y codifica en Base64.
    """
    # Configuración de límites para no saturar al LLM
    MAX_DIMENSION = 1024
    JPEG_QUALITY = 85

    @property
    def sensory_type(self) -> SensoryType:
        return SensoryType.VISUAL

    def _optimize_image(self, image_stream: io.BytesIO) -> str:
        """
        Redimensiona y comprime la imagen para eficiencia de tokens.
        Retorna la cadena base64.
        """
        with Image.open(image_stream) as img:
            # 1. Calcular nueva dimensión manteniendo aspect ratio
            width, height = img.size
            if width > self.MAX_DIMENSION or height > self.MAX_DIMENSION:
                ratio = min(self.MAX_DIMENSION / width, self.MAX_DIMENSION / height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.debug(f"   📉 Resizing image: {width}x{height} -> {new_size}")

            # 2. Convertir a RGB (por si llega un PNG con transparencia) y guardar en buffer
            if img.mode != "RGB":
                img = img.convert("RGB")

            output_buffer = io.BytesIO()
            img.save(output_buffer, format="JPEG", quality=self.JPEG_QUALITY)
            output_buffer.seek(0)
            
            # 3. Encode Base64
            return base64.b64encode(output_buffer.getvalue()).decode('utf-8')

    async def process(self, update: Update) -> dict[str, Any] | None:
        if not update.message or not update.message.photo:
            return None

        start_time = time.time()
        
        try:
            # Seleccionamos la foto de mayor resolución (la última de la lista)
            photo = update.message.photo[-1]
            file_id = photo.file_id
            
            logger.info("📸 Visual processing: file_id=%s dimensions=%sx%s", file_id[:10], photo.width, photo.height)

            # Obtenemos el objeto Bot para descargar el archivo
            bot = update.get_bot()
            if not bot:
                logger.error("❌ VisualDriver: Could not retrieve Bot instance from Update.")
                return None

            # Descarga en memoria (Non-blocking IO)
            logger.debug("⬇️ Downloading image file...")
            download_start = time.time()
            new_file = await bot.get_file(file_id)
            img_buffer = io.BytesIO()
            await new_file.download_to_memory(out=img_buffer)
            img_buffer.seek(0)
            download_elapsed = time.time() - download_start
            logger.debug("✅ Download complete: %.2fs", download_elapsed)

            # Procesamiento de imagen (CPU bound - debería ser rápido para <1024px)
            logger.debug("🖼️ Optimizing image...")
            optimize_start = time.time()
            base64_image = self._optimize_image(img_buffer)
            optimize_elapsed = time.time() - optimize_start
            logger.debug("✅ Optimization complete: %.2fs base64_len=%d", optimize_elapsed, len(base64_image))
            
            # Construcción del Payload Multimodal
            caption = update.message.caption or ""
            
            payload = {
                "role": "user",
                "content": [
                    # Si hay caption, lo metemos como texto. Si no, metemos un placeholder contextual.
                    {"type": "text", "text": caption if caption else "Analyze this image."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
            
            total_elapsed = time.time() - start_time
            logger.info("✅ Visual processing complete: file_id=%s total_time=%.2fs", file_id[:10], total_elapsed)
            return payload

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("❌ VisualDriver error after %.2fs: %s", elapsed, str(e), exc_info=True)
            return None