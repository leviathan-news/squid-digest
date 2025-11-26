"""Tests for email formatting and subject line changes."""

import pytest
from datetime import datetime
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
from squid_digest.email.templates import public_digest_template


class TestEmailSubjectAndH1:
    """Test that email subject line and H1 use squid emoji and correct format."""
    
    def test_send_digest_email_subject_line(self):
        """Test that send_digest_email uses squid emoji and 'Leviathan News Daily Digest'."""
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
                
                # Check that create_post was called with correct title
                call_args = mock_request.call_args_list
                
                # Find the POST request to create the post
                # _make_request is called as: _make_request("POST", "posts", data)
                # So call[0] = ("POST", "posts", data) and call[1] = {}
                post_call = None
                for call in call_args:
                    if len(call[0]) >= 2 and call[0][0] == "POST" and call[0][1] == "posts":
                        post_call = call
                        break
                
                assert post_call is not None, "create_post should have been called"
                
                # Check the post data - data is the third positional arg
                post_data_dict = post_call[0][2]  # Third positional arg is the data dict
                post_data = post_data_dict['posts'][0]
                
                title = post_data['title']
                status = post_data['status']
                
                # Verify subject line format
                assert "🦑" in title, "Subject should contain squid emoji"
                assert "Leviathan News Daily Digest" in title, "Subject should contain 'Leviathan News Daily Digest'"
                assert "Crypto Trading Signals" not in title, "Subject should NOT contain old 'Crypto Trading Signals'"
                
                # Verify status is published (not draft)
                assert status == "published", f"Post should be published, got {status}"
                
            finally:
                Path(temp_path).unlink()
    
    def test_public_digest_template_h1(self):
        """Test that public_digest_template uses squid emoji and correct H1."""
        content = "<p>Test content</p>"
        date = "January 15, 2025"
        
        html = public_digest_template(content, date)
        
        # Check that the visible title H1 (first H1) contains squid emoji and correct text
        # Extract the first H1 tag content
        import re
        h1_matches = re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        assert len(h1_matches) > 0, "Should contain at least one h1 tag"
        
        # The first H1 should be the visible post title
        first_h1 = h1_matches[0].strip()
        assert "🦑" in first_h1, "First H1 should contain squid emoji"
        assert "Leviathan News Daily Digest" in first_h1, "First H1 should contain 'Leviathan News Daily Digest'"
        assert "Crypto Trading Signals" not in first_h1, "First H1 should NOT contain old 'Crypto Trading Signals'"
        
        # Verify there are h1 tags
        assert '<h1' in html and '</h1>' in html, "Should contain h1 tag"


class TestHTMLBlockquoteFormatting:
    """Test HTML blockquote formatting improvements."""
    
    def test_blockquote_formatting(self):
        """Test that blockquotes don't have quotes, em dashes, and have correct links."""
        client = GhostEmailClient()
        
        # Sample HTML with table structure that should be converted
        html_with_table = """
        <table>
        <tr>
            <td><img src="test.jpg"></td>
            <td>
                <strong><a href="story-url">Story Title</a></strong> - <a href="source-url">Source</a>
                <br><span>🏷️ Tags</span>
                <br>💬 <i>This is a comment</i> — @username
            </td>
        </tr>
        </table>
        """
        
        formatted = client._convert_table_to_story_layout(html_with_table)
        
        # Check blockquote formatting
        assert 'blockquote' in formatted, "Should contain blockquote"
        
        # Should NOT have quotes around comment
        assert '"This is a comment"' not in formatted, "Comment should not be wrapped in quotes"
        assert 'This is a comment' in formatted, "Comment text should be present"
        
        # Should NOT have em dash before username
        assert '— @username' not in formatted, "Should not have em dash before username"
        
        # Should have correct username link (to /articles, not /comments)
        assert 'leviathannews.xyz/u/username/articles' in formatted, "Username should link to /articles"
        assert 'leviathannews.xyz/user/username/comments' not in formatted, "Should not link to /comments"
        
        # Should have smaller font size
        assert 'font-size: 14px' in formatted, "Blockquote should have font-size: 14px"


class TestFooterAndDisclaimer:
    """Test footer placement and disclaimer addition."""
    
    def test_footer_after_backtest(self):
        """Test that footer and disclaimer are added after backtest section."""
        # This would require mocking the full digest generation
        # For now, we'll test the logic by checking the script structure
        
        # Read the digest.py script to verify footer placement
        script_path = Path(__file__).parent.parent / "scripts" / "digest.py"
        script_content = script_path.read_text()
        
        # Footer should be added after backtest_section is appended
        assert 'full_writeup += backtest_section' in script_content, "Backtest should be appended first"
        assert 'full_writeup += "\\n\\n---\\n"' in script_content or 'full_writeup += \'\\n\\n---\\n\'' in script_content, "Footer separator should be added"
        assert 'Generated by Squid Digest' in script_content, "Footer text should be present"
        assert 'Disclaimer:' in script_content, "Disclaimer should be present"
        
        # Find the order: backtest should come before footer
        backtest_idx = script_content.find('full_writeup += backtest_section')
        disclaimer_idx = script_content.find('Disclaimer:')
        
        assert backtest_idx != -1, "Backtest append should be found"
        assert disclaimer_idx != -1, "Disclaimer should be present"
        # Verify order: backtest comes before disclaimer (which is part of footer)
        assert backtest_idx < disclaimer_idx, f"Backtest (at {backtest_idx}) should be added before disclaimer/footer (at {disclaimer_idx})"


class TestBacktestFormatting:
    """Test backtest formatting improvements."""
    
    def test_backtest_bullet_points(self):
        """Test that backtest summary stats use bullet points."""
        from squid_digest.backtest.newsletter_formatter import format_backtest_for_newsletter
        
        # Mock backtest results
        results = {
            'portfolio_value': 10000.50,
            'total_return': 5.25,
            'initial_capital': 10000.0,
            'days_since_start': 10,
            'start_date': datetime(2025, 1, 1),
            'current_date': datetime(2025, 1, 11),
            'positions': [],
            'trades_today': [],
            'benchmark_returns': {'BTC': 3.0, 'BTC_ETH': 4.0},
            'cash': 5000.0
        }
        
        formatted = format_backtest_for_newsletter(results)
        
        # Check that summary stats use bullet points
        assert '- **Portfolio Value:**' in formatted, "Portfolio Value should use bullet point"
        assert '- **Total Return:**' in formatted, "Total Return should use bullet point"
        assert '- **Days Since Start:**' in formatted, "Days Since Start should use bullet point"
        assert '- **Cash:**' in formatted, "Cash should use bullet point"
        
        # Check that cash is in the main section (before Performance vs Benchmarks)
        cash_idx = formatted.find('- **Cash:**')
        benchmarks_idx = formatted.find('### Performance vs Benchmarks')
        
        assert cash_idx < benchmarks_idx, "Cash should appear before Performance vs Benchmarks"
        
        # Check that cash is NOT duplicated at the end
        cash_occurrences = formatted.count('- **Cash:**')
        assert cash_occurrences == 1, f"Cash should appear exactly once, found {cash_occurrences} times"
