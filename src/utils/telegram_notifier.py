"""
Telegram Notification Utility
Sends direct messages to users by telegram_id
"""
import os
import logging
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class TelegramNotifier:
    _token: str | None = None
    _bot: Bot | None = None

    @classmethod
    def _get_bot(cls) -> Bot | None:
        """Lazy load and cache the Telegram bot instance."""
        if not cls._bot:
            token = os.getenv("TELEGRAM_TOKEN")
            if not token:
                logger.error("❌ TELEGRAM_TOKEN not configured. Cannot send notifications.")
                return None
            cls._bot = Bot(token=token)
        return cls._bot

    @classmethod
    async def send_event_notification(
        cls,
        telegram_id: str | int,
        event_summary: str,
        start_time: str,
        description: str = "",
        organizer_name: str = "",
    ) -> bool:
        """
        Send a Telegram message to notify a user about a scheduled event.
        
        Args:
            telegram_id: User's Telegram ID
            event_summary: Event title
            start_time: Event start time (ISO format or readable string)
            description: Event description
            organizer_name: Name of the event organizer
        
        Returns:
            True if message sent successfully, False otherwise
        """
        bot = cls._get_bot()
        if not bot:
            logger.error(f"❌ Telegram bot not initialized")
            return False

        try:
            # Build the notification message
            message = f"📅 **New Event Scheduled**\n\n"
            if organizer_name:
                message += f"👤 **Organizer:** {organizer_name}\n"
            message += f"📌 **Event:** {event_summary}\n"
            message += f"⏰ **Time:** {start_time}\n"
            if description:
                message += f"\n📝 **Details:**\n{description}\n"
            
            await bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown",
            )
            logger.info(f"✅ Telegram notification sent")
            return True

        except TelegramError as e:
            logger.debug(f"⚠️ Telegram API error: {type(e).__name__}")
            return False
        except Exception as e:
            logger.debug(f"⚠️ Error sending Telegram: {type(e).__name__}")
            return False
            
    @classmethod
    async def send_message(cls, telegram_id: str | int, message: str) -> bool:
        """
        Sends a simple text message to a user.
        """
        bot = cls._get_bot()
        if not bot:
            return False

        try:
            await bot.send_message(chat_id=telegram_id, text=message)
            logger.info(f"✅ Simple message sent to {telegram_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send simple message to {telegram_id}: {e}")
            return False
