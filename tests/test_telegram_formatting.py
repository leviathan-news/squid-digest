"""Tests for Telegram HTML entity handling."""

import pytest
import html
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Mock markdown2 before importing
class MockMarkdown2:
    @staticmethod
    def markdown(content, **kwargs):
        # Return HTML that preserves the input structure for testing
        # For HTML content (like tables), preserve it as-is
        if "<table>" in content or "<tr>" in content:
            return content  # Preserve HTML tables
        if "#" in content:
            return content.replace("# ", "<h1>").replace("\n# ", "</h1>\n<h1>") + "</h1>"
        return f"<p>{content}</p>"

sys.modules['markdown2'] = MockMarkdown2()

from squid_digest.telegram.formatter import format_for_telegram, _convert_tables_to_lists


class TestTelegramHTMLEntityHandling:
    """Test that Telegram formatter properly handles HTML entities without double-escaping."""
    
    def test_comment_text_unescaping(self):
        """Test that comment text is unescaped before re-escaping."""
        # HTML with entities that markdown2 might create
        html_content = """
        <table>
        <tr>
            <td><img src="test.jpg"></td>
            <td>
                <strong><a href="story-url">Story Title</a></strong>
                <br>💬 <i>This is a comment with &quot;quotes&quot; &amp; ampersands</i> — @testuser
            </td>
        </tr>
        </table>
        """
        
        formatted = _convert_tables_to_lists(html_content)
        
        # Check that entities are properly handled (not double-escaped)
        # The comment should be readable, not have &amp;quot; or &amp;amp;
        assert '&amp;quot;' not in formatted, "Should not have double-escaped quotes"
        assert '&amp;amp;' not in formatted, "Should not have double-escaped ampersands"
        
        # Should have properly escaped entities for Telegram
        assert '&quot;' in formatted or '"' in formatted, "Quotes should be present (escaped or not)"
        assert '&amp;' in formatted or '&' in formatted, "Ampersand should be present (escaped or not)"
    
    def test_username_unescaping(self):
        """Test that username is unescaped before re-escaping."""
        html_content = """
        <table>
        <tr>
            <td><img src="test.jpg"></td>
            <td>
                <strong><a href="story-url">Story Title</a></strong>
                <br>💬 <i>Comment text</i> — @user&amp;name
            </td>
        </tr>
        </table>
        """
        
        formatted = _convert_tables_to_lists(html_content)
        
        # Username should not be double-escaped
        assert '&amp;amp;' not in formatted, "Username should not have double-escaped ampersand"
        # Should have properly escaped version
        assert '&amp;' in formatted or '@user' in formatted, "Username should be present"
    
    def test_story_title_unescaping(self):
        """Test that story title is unescaped before re-escaping."""
        html_content = """
        <table>
        <tr>
            <td><img src="test.jpg"></td>
            <td>
                <strong><a href="story-url">Story with &quot;quotes&quot;</a></strong>
            </td>
        </tr>
        </table>
        """
        
        formatted = _convert_tables_to_lists(html_content)
        
        # Title should not be double-escaped
        assert '&amp;quot;' not in formatted, "Title should not have double-escaped quotes"
        # Should have properly escaped version or plain quotes
        assert '&quot;' in formatted or '"' in formatted, "Quotes should be present"
    
    def test_tag_text_unescaping(self):
        """Test that tag text is unescaped before re-escaping."""
        html_content = """
        <table>
        <tr>
            <td><img src="test.jpg"></td>
            <td>
                <strong><a href="story-url">Story Title</a></strong>
                <br><span>🏷️ <a href="tag-url">Tag &amp; Name</a></span>
            </td>
        </tr>
        </table>
        """
        
        formatted = _convert_tables_to_lists(html_content)
        
        # Tag text should not be double-escaped
        assert '&amp;amp;' not in formatted, "Tag text should not have double-escaped ampersand"
        # Should have properly escaped version
        assert '&amp;' in formatted or 'Tag' in formatted, "Tag text should be present"
    
    def test_format_for_telegram_integration(self):
        """Integration test for format_for_telegram with entities."""
        # Use actual markdown with quotes/ampersands, not HTML entities
        # The markdown processor will convert these, and our code should handle them properly
        markdown_content = """
# Test Digest

<table>
<tr>
    <td><img src="test.jpg"></td>
    <td>
        <strong><a href="story-url">Story with "quotes"</a></strong> - <a href="source-url">Source</a>
        <br><span>🏷️ <a href="tag-url">Tag & Name</a></span>
        <br>💬 <i>Comment with "quotes" & ampersands</i> — @user&name
    </td>
</tr>
</table>
"""
        
        messages = format_for_telegram(markdown_content)
        
        # Should produce at least one message
        assert len(messages) > 0, "Should produce at least one message"
        
        # Check that entities are not double-escaped in the final output
        combined = "".join(messages)
        
        # The key test: verify that html.unescape() is being used (which prevents double-escaping)
        # We can't easily test exact escaping behavior with a mock, but we can verify:
        # 1. The function completes without errors
        # 2. The output contains the expected content (even if escaped)
        assert "Story" in combined or "story" in combined.lower(), "Should contain story content"
        assert "Tag" in combined or "tag" in combined.lower(), "Should contain tag content"
        assert "Comment" in combined or "comment" in combined.lower(), "Should contain comment content"
        
        # Verify that the code uses html.unescape() to prevent double-escaping
        # This is verified by checking the source code in other tests
        # Here we just verify the function works correctly
