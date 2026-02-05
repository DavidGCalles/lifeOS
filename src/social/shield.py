# src/social/shield.py
import logging
from typing import Tuple
from telegram import Update, MessageEntity
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

class SocialShield:
    """
    FR-16: The Shield (Group Governance Middleware).
    Determina si el bot debe participar en una conversación o mantenerse en silencio (Default Silence).
    """

    @staticmethod
    async def should_engage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[bool, str|None]:
        """
        Analiza el update para decidir si se activa el 'Reasoning Core'.

        Returns:
            tuple: (should_respond: bool, sanitized_text: Optional[str])
                   sanitized_text is the cleaned message to forward to the Orchestrator
                   (handle stripped) when activation was via mention. Otherwise None.
        """
        if not update.effective_chat or not update.message:
            return False, None

        chat_type = update.effective_chat.type
        
        # 1. CHATS PRIVADOS: Siempre activo (Pase VIP)
        if chat_type == 'private':
            # For private chats we forward the raw text (no stripping)
            return True, (update.message.text if getattr(update.message, 'text', None) else None)

        # 2. GRUPOS: Protocolo de "Solo si se me habla"
        if chat_type in ['group', 'supergroup']:
            return await SocialShield._has_activation_trigger(update, context)

        # Por defecto (Canales, etc), silencio.
        return False, None

    @staticmethod
    async def _has_activation_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[bool, str|None]:
        """Devuelve (activated: bool, sanitized_text: Optional[str]).

        Si la activación es por REPLY, devuelve el original sin cambios.
        Si la activación es por MENTION, devuelve el texto con las @menciones al bot eliminadas y saneado.
        """
        message = update.message
        bot = context.bot
        text = message.text or ""

        # A. Reply Trigger: ¿El usuario está respondiendo a un mensaje del bot?
        if message.reply_to_message:
            # Comprobamos si el autor del mensaje original es el bot
            if message.reply_to_message.from_user.id == bot.id:
                logger.info(f"🛡️ Shield: Activation via REPLY in group {update.effective_chat.id}")
                return True, text.strip() if text else ""

        # B. Mention Trigger: ¿Hay una @mención al bot?
        bot_username = (bot.username or "").lstrip('@')
        if not bot_username:
            return False, None

        # Guardamos rangos a remover (start, end)
        remove_ranges: list[tuple[int,int]] = []

        if message.entities:
            for entity in message.entities:
                if entity.type == MessageEntity.MENTION:
                    # Extraemos el texto de la mención
                    start, end = entity.offset, entity.offset + entity.length
                    mention_text = text[start:end]
                    # Normalizamos y comparamos sin @
                    if mention_text.lstrip('@').lower() == bot_username.lower():
                        remove_ranges.append((start, end))
                elif entity.type == MessageEntity.TEXT_MENTION and getattr(entity, 'user', None):
                    if entity.user.id == bot.id:
                        start, end = entity.offset, entity.offset + entity.length
                        remove_ranges.append((start, end))

        if remove_ranges:
            logger.info(f"🛡️ Shield: Activation via MENTION (@{bot_username}) in group {update.effective_chat.id}")
            # Reconstruimos el texto sin los rangos
            parts = []
            last = 0
            for (s, e) in sorted(remove_ranges):
                if last < s:
                    parts.append(text[last:s])
                last = e
            if last < len(text):
                parts.append(text[last:])
            sanitized = "".join(parts)
            # Normalizamos espacios
            import re
            sanitized = re.sub(r"\s+", " ", sanitized).strip()
            return True, sanitized

        # Si llega aquí, es ruido de fondo.
        logger.debug(f"🛡️ Shield: Ignoring background noise in group {update.effective_chat.id}")
        return False, None