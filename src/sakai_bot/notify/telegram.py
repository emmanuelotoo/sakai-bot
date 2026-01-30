"""
Telegram Bot API client.

Sends notifications via Telegram Bot API.
https://core.telegram.org/bots/api
"""

import logging
from typing import Optional

import requests

from sakai_bot.config import get_settings

logger = logging.getLogger(__name__)

# Telegram Bot API endpoint
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    """
    Telegram Bot API client for sending notifications.
    
    Uses Telegram's Bot API to send text messages to a configured
    chat (user, group, or channel).
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        """
        Initialize Telegram notifier.
        
        Args:
            token: Telegram Bot API token (from @BotFather)
            chat_id: Telegram chat ID (user, group, or channel)
        """
        settings = get_settings()
        
        self.token = token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id
        
        self.api_url = TELEGRAM_API_URL.format(token=self.token)
        self.session = requests.Session()
    
    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a text message via Telegram.
        
        Args:
            message: The message text to send
            parse_mode: Message formatting mode (Markdown or HTML)
            
        Returns:
            bool: True if message was sent successfully
        """
        # Convert WhatsApp-style formatting to Telegram Markdown
        # WhatsApp uses *bold* which is the same as Telegram Markdown
        
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        
        try:
            response = self.session.post(self.api_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    message_id = data.get("result", {}).get("message_id", "unknown")
                    logger.info(f"Telegram message sent successfully: {message_id}")
                    return True
                else:
                    logger.error(f"Telegram API error: {data.get('description')}")
                    return False
            else:
                logger.error(
                    f"Telegram API error: {response.status_code} - {response.text}"
                )
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Telegram API request timed out")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram API request failed: {e}")
            return False
    
    def send_long_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a long message, splitting if necessary.
        
        Telegram has a 4096 character limit per message.
        
        Args:
            message: The message text to send
            parse_mode: Message formatting mode
            
        Returns:
            bool: True if all parts were sent successfully
        """
        MAX_LENGTH = 4000  # Leave some buffer
        
        if len(message) <= MAX_LENGTH:
            return self.send_message(message, parse_mode)
        
        # Split by double newlines to preserve formatting
        parts = []
        current_part = ""
        
        for paragraph in message.split("\n\n"):
            if len(current_part) + len(paragraph) + 2 > MAX_LENGTH:
                if current_part:
                    parts.append(current_part.strip())
                current_part = paragraph
            else:
                current_part += "\n\n" + paragraph if current_part else paragraph
        
        if current_part:
            parts.append(current_part.strip())
        
        # Send all parts
        success = True
        for i, part in enumerate(parts):
            if i > 0:
                part = f"(...continued)\n\n{part}"
            if not self.send_message(part, parse_mode):
                success = False
        
        return success
    
    def test_connection(self) -> bool:
        """
        Test if the bot token and chat ID are valid.
        
        Returns:
            bool: True if connection is valid
        """
        try:
            # Use getMe to verify token
            response = self.session.get(
                f"https://api.telegram.org/bot{self.token}/getMe",
                timeout=10
            )
            if response.status_code == 200 and response.json().get("ok"):
                bot_info = response.json().get("result", {})
                logger.info(f"Connected to Telegram bot: @{bot_info.get('username')}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            return False
