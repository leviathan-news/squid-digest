"""Integration tests that simulate the GitHub workflow steps."""

import unittest
import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestGitHubWorkflowSimulation(unittest.TestCase):
    """Tests that simulate the exact GitHub workflow code."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent
        self.writeup_dir = self.project_root / "writeup"
    
    def test_workflow_imports(self):
        """Test that workflow imports work correctly."""
        # This is the exact import from the workflow
        try:
            from squid_digest.telegram import TelegramClient, format_for_telegram
        except ImportError as e:
            self.fail(f"Workflow imports failed: {e}")
    
    def test_workflow_file_reading(self):
        """Test reading signals file as workflow does."""
        # Simulate workflow logic: find today's signals file
        # In workflow: TODAY=$(date -u '+%Y-%m-%d')
        # We'll use a known signals file instead
        
        signals_files = list(self.writeup_dir.rglob("signals_*.md"))
        if not signals_files:
            self.skipTest("No signals files found for testing")
        
        # Use the most recent signals file
        signals_file = sorted(signals_files)[-1]
        
        # Simulate workflow: signals_path = Path('$SIGNALS_FILE')
        signals_path = Path(signals_file)
        
        # Check file exists (workflow does this)
        self.assertTrue(signals_path.exists(), "Signals file does not exist")
        
        # Read content (workflow does: content = signals_path.read_text())
        content = signals_path.read_text()
        self.assertGreater(len(content), 0, "Signals file is empty")
    
    def test_workflow_formatting(self):
        """Test formatting as workflow does."""
        # Get a signals file
        signals_files = list(self.writeup_dir.rglob("signals_*.md"))
        if not signals_files:
            self.skipTest("No signals files found for testing")
        
        signals_file = sorted(signals_files)[-1]
        signals_path = Path(signals_file)
        
        # Read content
        content = signals_path.read_text()
        
        # Format (workflow does: messages = format_for_telegram(content))
        from squid_digest.telegram import format_for_telegram
        
        messages = format_for_telegram(content)
        
        # Validate
        self.assertIsInstance(messages, list)
        self.assertGreater(len(messages), 0, "No messages generated")
        
        # Check message lengths (workflow validates this)
        for i, msg in enumerate(messages, 1):
            self.assertLessEqual(len(msg), 4096, 
                               f"Message {i} exceeds Telegram limit")
    
    def test_workflow_telegram_client_init(self):
        """Test TelegramClient initialization as workflow does."""
        from squid_digest.telegram import TelegramClient
        
        # Workflow checks env vars before initializing
        # We'll test that initialization requires credentials
        original_token = os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        original_channel = os.environ.pop("TELEGRAM_CHANNEL_ID", None)
        
        try:
            # Should raise ValueError without credentials
            with self.assertRaises(ValueError):
                TelegramClient()
        finally:
            # Restore env vars
            if original_token:
                os.environ["TELEGRAM_BOT_TOKEN"] = original_token
            if original_channel:
                os.environ["TELEGRAM_CHANNEL_ID"] = original_channel
    
    def test_workflow_full_flow(self):
        """Test the full workflow flow without actually sending."""
        # Get a signals file
        signals_files = list(self.writeup_dir.rglob("signals_*.md"))
        if not signals_files:
            self.skipTest("No signals files found for testing")
        
        signals_file = sorted(signals_files)[-1]
        signals_path = Path(signals_file)
        
        # Simulate full workflow steps
        from squid_digest.telegram import TelegramClient, format_for_telegram
        
        # Step 1: Validate file exists
        self.assertTrue(signals_path.exists())
        
        # Step 2: Read content
        content = signals_path.read_text()
        self.assertGreater(len(content), 0)
        
        # Step 3: Format content
        messages = format_for_telegram(content)
        self.assertGreater(len(messages), 0)
        
        # Step 4: Validate message lengths
        for msg in messages:
            self.assertLessEqual(len(msg), 4096)
        
        # Step 5: Check that client can be initialized (if credentials exist)
        # We don't actually send, just verify the flow works
        has_credentials = (
            os.getenv("TELEGRAM_BOT_TOKEN") and 
            os.getenv("TELEGRAM_CHANNEL_ID")
        )
        
        if has_credentials:
            # If credentials exist, test initialization
            client = TelegramClient()
            self.assertIsNotNone(client)
        else:
            # If no credentials, that's fine - workflow handles this
            self.skipTest("Telegram credentials not configured (this is OK)")
    
    def test_workflow_error_handling(self):
        """Test error handling scenarios from workflow."""
        from squid_digest.telegram import format_for_telegram
        
        # Test 1: Empty file
        empty_messages = format_for_telegram("")
        # Should not crash, might return empty list or list with empty string
        
        # Test 2: Invalid markdown (should still work, markdown2 is forgiving)
        invalid_markdown = "<invalid>tags</invalid>"
        messages = format_for_telegram(invalid_markdown)
        self.assertIsInstance(messages, list)
        
        # Test 3: Very long content (should split)
        long_content = "# Test\n\n" + "A" * 10000
        messages = format_for_telegram(long_content, max_length=4096)
        self.assertGreater(len(messages), 1)


if __name__ == "__main__":
    unittest.main()
