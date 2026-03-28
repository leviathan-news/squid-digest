"""Tests for post status (published vs draft)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Mock environment variables before importing
os.environ.setdefault("GHOST_URL", "https://test.ghost.local")
os.environ.setdefault("GHOST_ADMIN_API_KEY", "test-id:test-secret")

# Mock markdown2 before importing ghost_client
class MockMarkdown2:
    @staticmethod
    def markdown(content, **kwargs):
        # Return simple HTML that can be processed by regex
        return f"<p>{content}</p>"

sys.modules['markdown2'] = MockMarkdown2()

from squid_digest.email.ghost_client import GhostEmailClient


class TestPostStatus:
    """Test that posts are created with correct status."""
    
    def test_send_digest_email_creates_published_post(self):
        """Test that send_digest_email creates posts with status='published'."""
        with patch('squid_digest.email.ghost_client.GhostEmailClient._make_request') as mock_request, \
             patch('squid_digest.email.ghost_client.GhostEmailClient.get_members') as mock_members, \
             patch('squid_digest.email.ghost_client.GhostEmailClient.send_email_to_members') as mock_send:
            
            # Mock responses
            mock_request.return_value = {"posts": [{"id": "test-post-id"}]}
            mock_members.return_value = []
            mock_send.return_value = True
            
            client = GhostEmailClient()
            
            # Create a temporary digest file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write("# Test Digest\n\nSome content")
                temp_path = f.name
            
            try:
                # Call send_digest_email
                client.send_digest_email(temp_path)
                
                # Check that post was created as draft, then published
                call_args = mock_request.call_args_list
                
                # Find the POST request to create the post (should be draft)
                post_call = None
                for call in call_args:
                    if len(call[0]) >= 2 and call[0][0] == "POST" and call[0][1] == "posts":
                        post_call = call
                        break
                
                assert post_call is not None, "create_post should have been called"
                
                # Check the post data - should be created as draft first
                post_data_dict = post_call[0][2]
                post_data = post_data_dict['posts'][0]
                initial_status = post_data['status']

                # Should be created as draft first
                assert initial_status == "draft", f"Post should be created as draft, got {initial_status}"

                # send_email_to_members should be called to publish + send email
                mock_send.assert_called_once_with("test-post-id", "label:subscriber")
                
            finally:
                Path(temp_path).unlink()
    
    def test_create_post_default_status(self):
        """Test that create_post defaults to draft (for admin notifications)."""
        with patch('squid_digest.email.ghost_client.GhostEmailClient._make_request') as mock_request:
            mock_request.return_value = {"posts": [{"id": "test-post-id"}]}
            
            client = GhostEmailClient()
            
            # Call create_post without status (should default to draft)
            client.create_post("Test Title", "<p>Test content</p>")
            
            # Check that it was called with status='draft'
            assert mock_request.called, "create_post should have been called"
            
            # Get the actual call - it's POST with endpoint "posts" and data as third positional arg
            # _make_request is called as: _make_request("POST", "posts", data)
            calls = [c for c in mock_request.call_args_list if len(c[0]) >= 2 and c[0][0] == "POST" and c[0][1] == "posts"]
            assert len(calls) > 0, "Should have called POST posts endpoint"
            call = calls[0]
            
            # call is a tuple: (args, kwargs)
            # args[0] = method, args[1] = endpoint, args[2] = data dict
            post_data_dict = call[0][2]  # Third positional arg is the data dict
            post_data = post_data_dict['posts'][0]
            status = post_data['status']
            
            assert status == "draft", f"Default status should be draft, got {status}"
