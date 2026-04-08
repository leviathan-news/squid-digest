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
        disable_web_page_preview: bool = True,
        chat_id: Optional[str] = None,
        message_thread_id: Optional[int] = None,
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
            "chat_id": chat_id or self.channel_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
            "disable_web_page_preview": disable_web_page_preview,
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        
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

    @staticmethod
    def _truncate_caption(html_content: str, max_length: int) -> str:
        """Truncate HTML caption to fit a hard character limit.

        Unlike truncate_html_safely (designed for 4096-char messages),
        this guarantees the returned string is <= max_length by reserving
        space for closing tags and omitting the truncation notice.
        """
        import re as _re

        if len(html_content) <= max_length:
            return html_content

        tag_pattern = _re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)[^>]*>')
        self_closing = {'br', 'img', 'hr', 'input', 'meta', 'link'}

        # Estimate worst-case closing-tag overhead: count open tags in first max_length chars
        # Each closing tag is at most </blockquote> = 13 chars
        # Reserve generous space: 100 chars for closing tags
        reserve = 100
        cut_point = max_length - reserve

        truncated = html_content[:cut_point]

        # Don't cut inside a tag
        last_open = truncated.rfind('<')
        if last_open != -1 and '>' not in truncated[last_open:]:
            truncated = truncated[:last_open]

        # Track unclosed tags
        tag_stack = []
        for match in tag_pattern.finditer(truncated):
            is_closing = match.group(1) == '/'
            tag_name = match.group(2).lower()
            if tag_name in self_closing:
                continue
            if is_closing:
                if tag_stack and tag_stack[-1] == tag_name:
                    tag_stack.pop()
            else:
                tag_stack.append(tag_name)

        # Close open tags
        for tag_name in reversed(tag_stack):
            truncated += f'</{tag_name}>'

        # Final guarantee: if still over (shouldn't happen with 100-char reserve), hard cut
        if len(truncated) > max_length:
            truncated = truncated[:max_length]

        return truncated

    # --- New methods for distribution enhancement ---

    def send_photo(
        self,
        photo_url: str,
        caption: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        message_thread_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a photo with caption via Telegram sendPhoto API.

        Args:
            photo_url: Public URL of the image (Telegram fetches it server-side)
            caption: Caption text (max 1024 chars — safely truncated if over)
            chat_id: Target channel/chat (defaults to self.channel_id)
            parse_mode: Parse mode for caption formatting
            message_thread_id: Forum topic thread ID (for posting in forum groups)
        """
        if len(caption) > 1024:
            caption = self._truncate_caption(caption, 1024)

        url = f"{self.api_url}/sendPhoto"
        payload = {
            "chat_id": chat_id or self.channel_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": parse_mode,
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            error_details = {}
            try:
                error_details = e.response.json()
            except Exception:
                error_details = {"error": str(e)}
            print(f"sendPhoto error: {e.response.status_code} — {error_details}")
            raise

    def edit_message(
        self,
        message_id: int,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
    ) -> Dict[str, Any]:
        """Edit an existing message via editMessageText.

        Args:
            message_id: ID of the message to edit
            text: New message text
            chat_id: Channel to edit in (defaults to self.channel_id)
            parse_mode: Parse mode for message formatting
            disable_web_page_preview: Disable link previews
        """
        url = f"{self.api_url}/editMessageText"
        payload = {
            "chat_id": chat_id or self.channel_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
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
            except Exception:
                error_details = {"error": str(e)}
            print(f"editMessageText error: {e.response.status_code} — {error_details}")
            raise

    def forward_message(
        self,
        from_chat_id: str,
        message_id: int,
        to_chat_id: str,
    ) -> Dict[str, Any]:
        """Forward a message from one chat to another.

        Args:
            from_chat_id: Source channel/chat ID
            message_id: ID of the message to forward
            to_chat_id: Destination channel/chat ID
        """
        url = f"{self.api_url}/forwardMessage"
        payload = {
            "chat_id": to_chat_id,
            "from_chat_id": from_chat_id,
            "message_id": message_id,
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
            except Exception:
                error_details = {"error": str(e)}
            print(f"forwardMessage error: {e.response.status_code} — {error_details}")
            raise

    @staticmethod
    def get_message_link(chat_id: str, message_id: int) -> Optional[str]:
        """Build a deep link to a specific message.

        Uses ``TELEGRAM_CHANNEL_USERNAME`` env var for public channels,
        falls back to ``t.me/c/…`` format for private supergroups (IDs
        starting with ``-100``), and returns ``None`` otherwise.
        """
        username = os.getenv("TELEGRAM_CHANNEL_USERNAME")
        if username:
            username = username.lstrip("@")
            return f"https://t.me/{username}/{message_id}"

        chat_str = str(chat_id)
        if chat_str.startswith("-100"):
            stripped = chat_str[4:]  # remove "-100" prefix
            return f"https://t.me/c/{stripped}/{message_id}"

        return None

