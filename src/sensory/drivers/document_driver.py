import io
import logging
import base64
from typing import Any
from telegram import Update
from src.sensory.base_driver import SensoryDriver, SensoryType
from src.utils.vision_parser import render_document_to_images, vision_extract_text

logger = logging.getLogger(__name__)

class DocumentDriver(SensoryDriver):
    """
    Driver encargado de procesar documentos (PDFs, imágenes como documentos y archivos de texto).
    Utiliza Vision Parser para PDFs/imágenes y lectura directa para archivos de texto.
    """

    @property
    def sensory_type(self) -> SensoryType:
        return SensoryType.DOCUMENT

    async def process(self, update: Update) -> dict[str, Any] | None:
        if not update.message or not update.message.document:
            return None

        doc = update.message.document
        mime_type = doc.mime_type or ""
        file_name = doc.file_name or "document"
        
        logger.info(f"   📄 Processing document: {file_name} ({mime_type})")

        try:
            bot = update.get_bot()
            new_file = await bot.get_file(doc.file_id)
            file_buffer = io.BytesIO()
            await new_file.download_to_memory(out=file_buffer)
            file_content = file_buffer.getvalue()

            extracted_text = ""

            # 1. Handle PDF
            if mime_type == 'application/pdf' or file_name.lower().endswith('.pdf'):
                logger.info(f"   Rendering PDF to images and extracting text...")
                images = render_document_to_images(file_content)
                extracted_text = await vision_extract_text(images)
            
            # 2. Handle Images (sent as documents)
            elif mime_type.startswith('image/') or any(file_name.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
                logger.info(f"   Processing image document via Vision Parser...")
                # Encode single image to base64
                base64_image = base64.b64encode(file_content).decode('utf-8')
                extracted_text = await vision_extract_text([base64_image])
            
            # 3. Handle Text Files
            elif mime_type.startswith('text/') or any(file_name.lower().endswith(ext) for ext in ['.txt', '.md', '.py', '.js', '.json', '.yaml', '.yml']):
                logger.info(f"   Reading text document...")
                extracted_text = file_content.decode('utf-8', errors='ignore')
            
            else:
                logger.warning(f"   Unsupported document type: {mime_type} ({file_name}).")
                return None

            if not extracted_text:
                logger.warning("   No text extracted from document.")
                return None

            # Prepare payload for Cortex
            # Inject with header [INCOMING DOCUMENT]
            caption = update.message.caption or ""
            header = f"[INCOMING DOCUMENT: {file_name}]"
            
            metadata = []
            if caption:
                metadata.append(f"Caption: {caption}")
            if mime_type:
                metadata.append(f"MIME Type: {mime_type}")
            
            metadata_str = "\n".join(metadata)
            if metadata_str:
                header += f"\n{metadata_str}"
            
            full_content = f"{header}\n\nCONTENT:\n{extracted_text}"
            
            payload = {
                "role": "user",
                "content": full_content,
                "metadata": {
                    "input_type": "document"
                }
            }
            
            logger.info(f"   ✅ Document processed successfully: {file_name}")
            return payload

        except Exception as e:
            logger.error(f"❌ DocumentDriver Error: {e}", exc_info=True)
            return None
