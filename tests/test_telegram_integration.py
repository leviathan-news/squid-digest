"""Integration tests for Telegram formatting and posting functionality."""

import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.telegram import TelegramClient, format_for_telegram


class TestTelegramIntegration(unittest.TestCase):
    """Integration tests for Telegram formatting and posting."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.writeup_dir = Path(__file__).parent.parent / "writeup"
    
    def test_format_real_signals_file(self):
        """Test formatting a real signals file from writeup directory."""
        # Find a signals file
        signals_files = list(self.writeup_dir.rglob("signals_*.md"))
        if not signals_files:
            self.skipTest("No signals files found in writeup/ (this is OK if no signals have been generated yet)")
        
        # Use the most recent one
        signals_file = sorted(signals_files)[-1]
        
        # Read content
        content = signals_file.read_text()
        self.assertGreater(len(content), 0, "Signals file is empty")
        
        # Format for Telegram
        messages = format_for_telegram(content)
        
        # Validate output
        self.assertIsInstance(messages, list)
        self.assertGreater(len(messages), 0, "No messages generated")
        
        # Validate each message
        for i, msg in enumerate(messages, 1):
            self.assertIsInstance(msg, str, f"Message {i} is not a string")
            self.assertGreater(len(msg), 0, f"Message {i} is empty")
            self.assertLessEqual(len(msg), 4096, f"Message {i} exceeds Telegram limit")
            
            # Basic HTML validation - should have valid tags
            # Check that HTML entities are properly escaped (no double-escaping)
            self.assertNotIn("&amp;amp;", msg, f"Message {i} has double-escaped entities")
            self.assertNotIn("&amp;quot;", msg, f"Message {i} has double-escaped quotes")
            
            # Check that supported Telegram tags are present (if content has formatting)
            # This is a basic check - we don't require tags, but if they exist they should be valid
            if "<b>" in msg:
                # If we have opening <b>, we should have closing </b>
                self.assertEqual(msg.count("<b>"), msg.count("</b>"), 
                               f"Message {i} has mismatched <b> tags")
            
            if "<a href=" in msg:
                # If we have links, they should be properly formatted
                self.assertIn("</a>", msg, f"Message {i} has unclosed <a> tags")
                # Count opening and closing tags
                open_tags = msg.count("<a href=")
                close_tags = msg.count("</a>")
                self.assertEqual(open_tags, close_tags,
                               f"Message {i} has mismatched <a> tags")
    
    def test_format_empty_content(self):
        """Test formatting empty content."""
        messages = format_for_telegram("")
        self.assertIsInstance(messages, list)
        # Empty content might produce empty list or list with empty string
        # Both are acceptable
    
    def test_format_minimal_markdown(self):
        """Test formatting minimal markdown content."""
        content = "# Test Header\n\nThis is a test paragraph."
        messages = format_for_telegram(content)
        
        self.assertIsInstance(messages, list)
        self.assertGreater(len(messages), 0)
        self.assertLessEqual(len(messages[0]), 4096)
    
    def test_format_with_tables(self):
        """Test formatting content with tables (like signals files)."""
        # Sample table content similar to signals files
        content = """
# Test Signals

<table>
  <tr>
    <td><strong><a href="https://example.com">1. Test Story</a></strong> - <a href="https://source.com">Source</a></td>
  </tr>
</table>
"""
        messages = format_for_telegram(content)
        
        self.assertIsInstance(messages, list)
        self.assertGreater(len(messages), 0)
        
        # Should have converted table to list format
        # Tables should be removed, content should be preserved
        combined = "".join(messages)
        self.assertNotIn("<table>", combined)
        self.assertNotIn("<tr>", combined)
        self.assertNotIn("<td>", combined)
    
    def test_message_splitting(self):
        """Test that long content is split into multiple messages."""
        # Create content that exceeds 4096 characters
        long_content = "# Test\n\n" + "A" * 5000
        messages = format_for_telegram(long_content, max_length=4096)
        
        self.assertGreater(len(messages), 1, "Long content should be split into multiple messages")
        
        # All messages should be within limit
        for msg in messages:
            self.assertLessEqual(len(msg), 4096)
    
    def test_telegram_client_initialization(self):
        """Test TelegramClient initialization (without credentials)."""
        # This should raise ValueError if credentials are missing
        with self.assertRaises(ValueError):
            # Temporarily remove env vars if they exist
            import os
            original_token = os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            original_channel = os.environ.pop("TELEGRAM_CHANNEL_ID", None)
            
            try:
                TelegramClient()
            finally:
                # Restore env vars
                if original_token:
                    os.environ["TELEGRAM_BOT_TOKEN"] = original_token
                if original_channel:
                    os.environ["TELEGRAM_CHANNEL_ID"] = original_channel
    
    def test_html_entity_handling(self):
        """Test that HTML entities are handled correctly."""
        # Content with special characters that might be double-escaped
        content = """
# Test

**Story with & and < and > characters**

<a href="https://example.com?q=test&param=value">Link</a>
"""
        messages = format_for_telegram(content)
        
        self.assertGreater(len(messages), 0)
        combined = "".join(messages)
        
        # Should not have double-escaped entities
        self.assertNotIn("&amp;amp;", combined)
        self.assertNotIn("&amp;lt;", combined)
        self.assertNotIn("&amp;gt;", combined)
        
        # Should have properly escaped entities
        # Note: & in URLs should be &amp; in HTML
        if "&amp;" in combined:
            # If we have &amp;, it should be properly formatted
            self.assertNotIn("&amp;&amp;", combined)


class TestTelegramForumSupport(unittest.TestCase):
    """Tests for forum topic support (message_thread_id) in TelegramClient."""

    def test_send_message_payload_includes_thread_id(self):
        """When message_thread_id is passed, it should appear in the request payload."""
        import os
        from unittest.mock import patch, MagicMock

        # Create client with dummy credentials
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test:token", "TELEGRAM_CHANNEL_ID": "-100123"}):
            client = TelegramClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            client.send_message("test", message_thread_id=154, chat_id="-100456")

            call_kwargs = mock_client.post.call_args
            payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
            self.assertEqual(payload["message_thread_id"], 154)
            self.assertEqual(payload["chat_id"], "-100456")

    def test_send_message_omits_thread_id_when_none(self):
        """When message_thread_id is not passed, it should NOT be in the payload."""
        import os
        from unittest.mock import patch, MagicMock

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test:token", "TELEGRAM_CHANNEL_ID": "-100123"}):
            client = TelegramClient()

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            client.send_message("test")

            call_kwargs = mock_client.post.call_args
            payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
            self.assertNotIn("message_thread_id", payload)

    def test_send_photo_payload_includes_thread_id(self):
        """send_photo should include message_thread_id when provided."""
        import os
        from unittest.mock import patch, MagicMock

        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test:token"}):
            client = TelegramClient(require_channel=False)

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            client.send_photo(
                photo_url="https://example.com/img.jpg",
                caption="test caption",
                chat_id="-100789",
                message_thread_id=154,
            )

            call_kwargs = mock_client.post.call_args
            payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
            self.assertEqual(payload["message_thread_id"], 154)
            self.assertEqual(payload["chat_id"], "-100789")


if __name__ == "__main__":
    unittest.main()
