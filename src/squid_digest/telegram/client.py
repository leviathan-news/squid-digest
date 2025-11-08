"""Telegram bot client for Squid Digest."""

import os
from typing import Optional, Dict, Any
import httpx


class TelegramClient:
    """Client for sending messages via Telegram Bot API."""
    
    def __init__(self, bot_token: Optional[str] = None, channel_id: Optional[str] = None):
        """Initialize Telegram bot client.
        
        Args:
            bot_token: Telegram bot token. If None, will read from TELEGRAM_BOT_TOKEN env var.
            channel_id: Telegram channel ID. If None, will read from TELEGRAM_CHANNEL_ID env var.
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.channel_id = channel_id or os.getenv("TELEGRAM_CHANNEL_ID")
        
        if not self.bot_token:
            raise ValueError("Telegram bot token is required. Set TELEGRAM_BOT_TOKEN environment variable.")
        if not self.channel_id:
            raise ValueError("Telegram channel ID is required. Set TELEGRAM_CHANNEL_ID environment variable.")
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
        disable_web_page_preview: bool = True
    ) -> Dict[str, Any]:
        """Send a message to the configured Telegram channel.
        
        Args:
            text: Message text (HTML formatted if parse_mode is HTML)
            parse_mode: Parse mode for message formatting (HTML or Markdown)
            disable_notification: Send message silently
            disable_web_page_preview: Disable link previews
            
        Returns:
            Response from Telegram API
            
        Raises:
            httpx.HTTPStatusError: If the API request fails
        """
        url = f"{self.api_url}/sendMessage"
        
        payload = {
            "chat_id": self.channel_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
            "disable_web_page_preview": disable_web_page_preview
        }
        
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_details = {}
            try:
                error_details = e.response.json()
            except:
                error_details = {"error": str(e)}
            
            print(f"Telegram API error: {e.response.status_code}")
            print(f"Error details: {error_details}")
            raise
        except Exception as e:
            print(f"Telegram API request failed: {e}")
            raise
    
    def send_multiple_messages(
        self,
        messages: list[str],
        parse_mode: str = "HTML",
        disable_notification: bool = False
    ) -> list[Dict[str, Any]]:
        """Send multiple messages sequentially to the channel.
        
        Args:
            messages: List of message texts to send
            parse_mode: Parse mode for message formatting
            disable_notification: Send messages silently
            
        Returns:
            List of responses from Telegram API
        """
        results = []
        for i, message in enumerate(messages, 1):
            try:
                # Add part indicator if multiple messages
                if len(messages) > 1:
                    header = f"<b>Part {i}/{len(messages)}</b>\n\n"
                    full_message = header + message
                else:
                    full_message = message
                
                result = self.send_message(
                    full_message,
                    parse_mode=parse_mode,
                    disable_notification=disable_notification
                )
                results.append(result)
            except Exception as e:
                print(f"Failed to send message {i}/{len(messages)}: {e}")
                # Continue with remaining messages even if one fails
                results.append({"ok": False, "error": str(e)})
        
        return results


