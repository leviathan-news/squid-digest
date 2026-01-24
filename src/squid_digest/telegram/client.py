"""Telegram bot client for Squid Digest."""

import os
from typing import Optional, Dict, Any
import httpx
from .formatter import truncate_html_safely


class TelegramClient:
    """Client for sending messages via Telegram Bot API."""
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
        channel_id: Optional[str] = None,
        require_channel: bool = True,
    ):
        """Initialize Telegram bot client.

        Args:
            bot_token: Telegram bot token. If None, will read from TELEGRAM_BOT_TOKEN env var.
            channel_id: Telegram channel ID. If None, will read from TELEGRAM_CHANNEL_ID env var.
            require_channel: If True, raises error if channel_id is not set. Set to False
                           when only using send_to_cave() which specifies its own channel.
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.channel_id = channel_id or os.getenv("TELEGRAM_CHANNEL_ID")

        if not self.bot_token:
            raise ValueError("Telegram bot token is required. Set TELEGRAM_BOT_TOKEN environment variable.")
        if require_channel and not self.channel_id:
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
            ValueError: If text is empty or exceeds Telegram limit
            httpx.HTTPStatusError: If the API request fails
        """
        # Validate message
        if not isinstance(text, str):
            raise ValueError(f"text must be a string, got {type(text).__name__}")
        
        if not text.strip():
            raise ValueError("Message text cannot be empty")
        
        # Telegram has a 4096 character limit
        if len(text) > 4096:
            raise ValueError(
                f"Message exceeds Telegram limit of 4096 characters "
                f"(got {len(text)} characters). Split the message first."
            )
        
        # Basic HTML validation if parse_mode is HTML
        if parse_mode == "HTML":
            # Check for balanced tags (basic check)
            open_tags = text.count("<")
            close_tags = text.count(">")
            if open_tags != close_tags:
                # This is a warning, not an error - Telegram will handle it
                print(f"Warning: Potential HTML tag mismatch (open: {open_tags}, close: {close_tags})")
        
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
            
        Raises:
            ValueError: If messages is not a list or is empty
        """
        # Validate input
        if not isinstance(messages, list):
            raise ValueError(f"messages must be a list, got {type(messages).__name__}")
        
        if len(messages) == 0:
            raise ValueError("messages list cannot be empty")
        
        results = []
        for i, message in enumerate(messages, 1):
            try:
                # Add part indicator if multiple messages
                if len(messages) > 1:
                    header = f"<b>Part {i}/{len(messages)}</b>\n\n"
                    full_message = header + message
                    
                    # Check if adding header would exceed limit
                    if len(full_message) > 4096:
                        print(f"Warning: Message {i} with header exceeds 4096 chars, truncating safely")
                        # Truncate message safely to fit header
                        max_msg_len = 4096 - len(header) - 50  # Leave room for closing tags + truncation notice
                        message = truncate_html_safely(message, max_msg_len)
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
                import traceback
                traceback.print_exc()
                # Continue with remaining messages even if one fails
                results.append({"ok": False, "error": str(e)})
        
        return results

    def send_to_cave(
        self,
        message: str,
        canonical_url: str,
        github_url: str,
        cave_channel_id: Optional[str] = None,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
    ) -> Dict[str, Any]:
        """Send message to SQUID Cave with masthead and links.

        Args:
            message: Page 1 content (already formatted HTML)
            canonical_url: Link to full digest on web
            github_url: Link to markdown file on GitHub
            cave_channel_id: Override channel ID (defaults to TELEGRAM_CAVE_CHANNEL_ID env var)
            parse_mode: Parse mode for message formatting
            disable_notification: Send message silently

        Returns:
            Response from Telegram API

        Raises:
            ValueError: If cave channel ID is not configured
        """
        channel = cave_channel_id or os.getenv("TELEGRAM_CAVE_CHANNEL_ID")
        if not channel:
            raise ValueError(
                "SQUID Cave channel ID not configured. "
                "Set TELEGRAM_CAVE_CHANNEL_ID environment variable."
            )

        # Build message with masthead and links at the top (before content)
        telegram_channel = "https://t.me/+8A2-Ypry6ytjYTYx"
        masthead = (
            "🐙 <b>SQUID Digest</b>\n"
            f'📰 <a href="{canonical_url}">Web</a> • '
            f'<a href="{github_url}">GitHub</a> • '
            f'<a href="{telegram_channel}">Telegram</a>\n\n'
        )
        full_message = masthead + message

        # Check length and truncate if needed
        if len(full_message) > 4096:
            print(f"Warning: SQUID Cave message exceeds 4096 chars ({len(full_message)}), truncating")
            # Calculate available space for message content
            max_content_len = 4096 - len(masthead) - 50  # Leave room for closing tags
            message = truncate_html_safely(message, max_content_len)
            full_message = masthead + message

        # Send to cave channel (temporarily override channel_id)
        original_channel = self.channel_id
        try:
            self.channel_id = channel
            return self.send_message(
                full_message,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
            )
        finally:
            self.channel_id = original_channel

