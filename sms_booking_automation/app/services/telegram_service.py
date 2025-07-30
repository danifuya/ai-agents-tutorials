import os
import logging
import requests
from typing import Optional, Dict, Any, List, Union

logger = logging.getLogger(__name__)


class TelegramServiceError(Exception):
    """Base exception for Telegram service errors."""
    pass


class TelegramAPIError(TelegramServiceError):
    """Exception for Telegram API errors."""
    pass

# Telegram Bot API configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = "https://api.telegram.org/bot"
TELEGRAM_TARGET_CHAT_IDS = os.environ.get("TELEGRAM_TARGET_CHAT_IDS")


class TelegramService:
    def __init__(self):
        self.api_url = f"{TELEGRAM_API_URL}{TELEGRAM_BOT_TOKEN}"
        # Parse comma-separated chat IDs from environment variable
        self.target_chat_ids = [chat_id.strip() for chat_id in TELEGRAM_TARGET_CHAT_IDS.split(",") if chat_id.strip()]

    def _send_request(self, method: str, payload: dict) -> dict:
        """Send request to Telegram API and return response or raise exception."""
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN not configured")
            raise TelegramServiceError("Telegram bot token not configured")
            
        url = f"{self.api_url}/{method}"
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Successfully called Telegram API method '{method}' for chat {payload.get('chat_id')}")
            return result
        except requests.exceptions.HTTPError as e:
            logger.error(f"Telegram API HTTP error for method '{method}': {e.response.status_code} - {e.response.text}")
            raise TelegramAPIError(f"Telegram API error: HTTP {e.response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Telegram API method '{method}': {str(e)}")
            raise TelegramServiceError(f"Network error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error calling Telegram API method '{method}': {str(e)}")
            raise TelegramServiceError(f"Telegram request failed: {str(e)}")

    def send_message_to_targets(self, text: str, photo_url: Optional[str] = None):
        """Sends a message to all configured target chats."""
        if not self.target_chat_ids:
            logger.warning("No target chat IDs configured, skipping message sending.")
            raise TelegramServiceError("No target chat IDs configured")

        errors = []
        for chat_id in self.target_chat_ids:
            try:
                payload = {
                    "chat_id": chat_id,
                    "parse_mode": "Markdown",
                }
                if photo_url:
                    payload.update({"photo": photo_url, "caption": text})
                    self._send_request("sendPhoto", payload)
                else:
                    payload.update({"text": text})
                    self._send_request("sendMessage", payload)
            except Exception as e:
                error_msg = f"Failed to send to chat {chat_id}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        if errors:
            raise TelegramServiceError(f"Failed to send to some targets: {'; '.join(errors)}")

    def send_message(self, chat_id: str, text: str, photo_url: Optional[str] = None):
        """Sends a message to a specific chat."""
        payload = {
            "chat_id": chat_id,
            "parse_mode": "Markdown",
        }
        
        try:
            if photo_url:
                payload.update({"photo": photo_url, "caption": text})
                result = self._send_request("sendPhoto", payload)
            else:
                payload.update({"text": text})
                result = self._send_request("sendMessage", payload)
            
            logger.info(f"Successfully sent message to chat {chat_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to send message to chat {chat_id}: {str(e)}")
            raise  # Re-raise the original exception
