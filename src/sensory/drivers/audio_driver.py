import io
import logging
import time
import base64
from typing import Any
from telegram import Update
from pydub import AudioSegment
from src.utils.llm_router import LiteLLMRouter
from src.sensory.base_driver import SensoryDriver, SensoryType

logger = logging.getLogger(__name__)

class AudioDriver(SensoryDriver):
    """
    Driver auditivo con NORMALIZACIÓN.
    1. Descarga el audio crudo de Telegram (OGG/Opus).
    2. Lo normaliza a MP3 estándar usando FFmpeg.
    3. Envía el MP3 limpio al pool 'audio-model' para transcripción verbatim.
    """

    @property
    def sensory_type(self) -> SensoryType:
        return SensoryType.AUDIO

    def _normalize_audio(self, raw_audio: io.BytesIO) -> io.BytesIO:
        """
        Convierte cualquier formato de entrada a MP3 estándar (128k).
        Esto asegura que el LLM siempre reciba un formato 'digestible'.
        """
        try:
            # Pydub lee el stream de bytes. Telegram manda OGG.
            audio = AudioSegment.from_file(raw_audio, format="ogg")
            
            # Exportamos a un nuevo buffer en MP3
            output_buffer = io.BytesIO()
            audio.export(output_buffer, format="mp3", bitrate="128k")
            output_buffer.seek(0)
            
            logger.debug(f"   🔄 Audio Normalization: OGG -> MP3 ({len(raw_audio.getvalue())}b -> {len(output_buffer.getvalue())}b)")
            return output_buffer
            
        except Exception as e:
            logger.error(f"❌ FFmpeg Conversion Error: {e}")
            raise e

    async def _transcribe(self, audio_buffer: io.BytesIO) -> str:
        """
        Invoca al LLM (audio-model) con el audio ya normalizado.
        """
        start_time = time.time()
        logger.info("🎙️ Audio transcription starting: audio_size=%d bytes", len(audio_buffer.getvalue()))
        
        try:
            # 1. Codificar a Base64 (MP3)
            audio_b64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')
            
            # 2. Construir mensaje Multimodal (Formato OpenAI Audio)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Please transcribe this audio file verbatim. Output ONLY the text spoken, no intro, no outro, no timestamps."
                        },
                        {
                            "type": "input_audio", 
                            "input_audio": {
                                "data": audio_b64,
                                "format": "mp3" # Ahora garantizamos que es MP3
                            }
                        }
                    ]
                }
            ]

            # 3. Llamada al Pool (use embedded Router singleton)
            logger.debug("📤 Sending to audio-model for transcription...")
            llm_start = time.time()
            router = LiteLLMRouter()
            response = await router.acompletion(
                model="audio-model",
                messages=messages,
                temperature=0.0
            )
            llm_elapsed = time.time() - llm_start
            logger.debug("✅ Audio model responded in %.2fs", llm_elapsed)

            result = response.choices[0].message.content or ""
            total_elapsed = time.time() - start_time
            logger.info("✅ Transcription complete: len=%d total_time=%.2fs", len(result), total_elapsed)
            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("❌ Audio transcription failed after %.2fs: %s", elapsed, str(e), exc_info=True)
            return "[Error transcribiendo audio]"

    async def process(self, update: Update) -> dict[str, Any] | None:
        if not update.message or not update.message.voice:
            return None

        start_time = time.time()
        
        try:
            voice = update.message.voice
            logger.info("🎙️ Audio processing: duration=%ds file_id=%s", voice.duration, voice.file_id[:10])

            # 1. Descarga (IO Bound)
            logger.debug("⬇️ Downloading voice file...")
            download_start = time.time()
            bot = update.get_bot()
            new_file = await bot.get_file(voice.file_id)
            
            raw_buffer = io.BytesIO()
            await new_file.download_to_memory(out=raw_buffer)
            raw_buffer.seek(0)
            download_elapsed = time.time() - download_start
            logger.debug("✅ Download complete: %.2fs size=%d bytes", download_elapsed, len(raw_buffer.getvalue()))

            # 2. Normalización (CPU Bound - FFmpeg)
            # Convertimos a formato universal antes de pasar al cerebro
            logger.debug("🔄 Normalizing audio...")
            normalize_start = time.time()
            normalized_buffer = self._normalize_audio(raw_buffer)
            normalize_elapsed = time.time() - normalize_start
            logger.debug("✅ Normalization complete: %.2fs", normalize_elapsed)

            # 3. Transcripción (Network Bound - Gemini)
            logger.debug("🤖 Transcribing audio...")
            text = await self._transcribe(normalized_buffer)
            
            if not text:
                text = "[Audio vacío o ininteligible]"

            # Formateo final con prefijo para el contexto del Agente
            final_content = f"[VOICE NOTE]: {text}"

            total_elapsed = time.time() - start_time
            logger.info("✅ Audio processing complete: total_time=%.2fs result_len=%d", total_elapsed, len(final_content))

            return {
                "role": "user",
                "content": [{"type": "text", "text": final_content}],
                "metadata": {
                    "input_type": "voice",
                    "duration": voice.duration,
                    "format": "mp3", # Confirmamos el formato normalizado
                    "original_format": "ogg"
                }
            }

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("❌ AudioDriver failure after %.2fs: %s", elapsed, str(e), exc_info=True)
            return None