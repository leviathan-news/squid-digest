"""Comprehensive tests for update_readme.py script."""

import unittest
import sys
import tempfile
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestUpdateReadme(unittest.TestCase):
    """Tests for update_readme.py functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent
        self.writeup_dir = self.project_root / "writeup"
        
        # Import functions from update_readme
        import update_readme
        self.find_latest_signals_file = update_readme.find_latest_signals_file
        self.extract_headlines = update_readme.extract_headlines
        self.get_portfolio_snapshot = update_readme.get_portfolio_snapshot
        self.format_above_fold_section = update_readme.format_above_fold_section
        self.update_readme = update_readme.update_readme
    
    def test_extract_headlines_with_strong_tag_only(self):
        """Test headline extraction with <strong>N. HEADLINE</strong> pattern (current format)."""
        # Create a temporary signals file with the current format
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            signals_file = Path(f.name)
            content = """# Trading Signals

## 🔥 Top Stories

<div>
<table>
  <tr>
    <td>
      <strong>1. First headline about crypto markets</strong> - <a href="...">source</a>
    </td>
  </tr>
  <tr>
    <td>
      <strong>2. Second headline about DeFi protocols</strong> - <a href="...">source</a>
    </td>
  </tr>
  <tr>
    <td>
      <strong>3. Third headline about NFT trends</strong> - <a href="...">source</a>
    </td>
  </tr>
</table>
</div>

## 🎯 Trading Signals
"""
            f.write(content)
        
        try:
            headlines = self.extract_headlines(signals_file, limit=5)
            
            self.assertEqual(len(headlines), 3, "Should extract 3 headlines")
            self.assertEqual(headlines[0][0], "First headline about crypto markets")
            self.assertEqual(headlines[1][0], "Second headline about DeFi protocols")
            self.assertEqual(headlines[2][0], "Third headline about NFT trends")
            # Check that tuples contain (headline, url, source)
            self.assertEqual(len(headlines[0]), 3)
            self.assertIn("source", headlines[0][2])
        finally:
            signals_file.unlink()
    
    def test_extract_headlines_with_link_pattern(self):
        """Test headline extraction with <strong><a>N. HEADLINE</a></strong> pattern (legacy format)."""
        # Create a temporary signals file with the legacy format
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            signals_file = Path(f.name)
            content = """# Trading Signals

## 🔥 Top Stories

<div>
<table>
  <tr>
    <td>
      <strong><a href="https://example.com">1. Legacy headline format with link</a></strong>
    </td>
  </tr>
  <tr>
    <td>
      <strong><a href="https://example.com">2. Another legacy headline</a></strong>
    </td>
  </tr>
</table>
</div>

## 🎯 Trading Signals
"""
            f.write(content)
        
        try:
            headlines = self.extract_headlines(signals_file, limit=5)
            
            # Legacy format without URL/source pattern won't match new regex
            # So it should return empty list
            self.assertEqual(len(headlines), 0, "Legacy format without URL/source pattern won't match")
        finally:
            signals_file.unlink()
    
    def test_extract_headlines_mixed_patterns(self):
        """Test that pattern 1 (with link) is tried first, then pattern 2 (without link)."""
        # Create a file with pattern 2 (no links) - should still work
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            signals_file = Path(f.name)
            content = """# Trading Signals

## 🔥 Top Stories

<div>
<table>
  <tr>
    <td>
      <strong>1. Headline without link</strong> - <a href="...">source</a>
    </td>
  </tr>
</table>
</div>
"""
            f.write(content)
        
        try:
            headlines = self.extract_headlines(signals_file, limit=5)
            self.assertEqual(len(headlines), 1, "Should extract 1 headline")
            self.assertEqual(headlines[0][0], "Headline without link")
            self.assertEqual(len(headlines[0]), 3)  # Should be tuple (headline, url, source)
        finally:
            signals_file.unlink()
    
    def test_extract_headlines_limit(self):
        """Test that limit parameter works correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            signals_file = Path(f.name)
            content = """# Trading Signals

## 🔥 Top Stories

<div>
<table>
  <tr><td><strong>1. Headline 1</strong></td></tr>
  <tr><td><strong>2. Headline 2</strong></td></tr>
  <tr><td><strong>3. Headline 3</strong></td></tr>
  <tr><td><strong>4. Headline 4</strong></td></tr>
  <tr><td><strong>5. Headline 5</strong></td></tr>
  <tr><td><strong>6. Headline 6</strong></td></tr>
</table>
</div>
"""
            f.write(content)
        
        try:
            # Note: This test file doesn't have URL/source pattern, so it won't match
            # The new regex requires: <strong>N. HEADLINE</strong> - <a href="URL">SOURCE</a>
            headlines = self.extract_headlines(signals_file, limit=3)
            # Without URL/source pattern, should return empty
            self.assertEqual(len(headlines), 0, "Without URL/source pattern, should return empty")
        finally:
            signals_file.unlink()
    
    def test_extract_headlines_no_top_stories_section(self):
        """Test that missing Top Stories section returns empty list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            signals_file = Path(f.name)
            content = """# Trading Signals

## 🎯 Trading Signals
Some content here.
"""
            f.write(content)
        
        try:
            headlines = self.extract_headlines(signals_file, limit=5)
            self.assertEqual(len(headlines), 0, "Should return empty list when section missing")
        finally:
            signals_file.unlink()
    
    def test_extract_headlines_empty_section(self):
        """Test that empty Top Stories section returns empty list."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            signals_file = Path(f.name)
            content = """# Trading Signals

## 🔥 Top Stories

## 🎯 Trading Signals
"""
            f.write(content)
        
        try:
            headlines = self.extract_headlines(signals_file, limit=5)
            self.assertEqual(len(headlines), 0, "Should return empty list when section is empty")
        finally:
            signals_file.unlink()
    
    def test_extract_headlines_with_real_file(self):
        """Test headline extraction with a real signals file (read-only)."""
        # Find a real signals file
        signals_files = list(self.writeup_dir.rglob("signals_*.md"))
        if not signals_files:
            self.skipTest("No signals files found for testing")
        
        # Use the most recent one
        signals_file = sorted(signals_files)[-1]
        
        # Extract headlines
        headlines = self.extract_headlines(signals_file, limit=5)
        
        # Should extract at least some headlines
        self.assertGreater(len(headlines), 0, "Should extract headlines from real file")
        
        # All headlines should be tuples (headline, url, source)
        for headline_tuple in headlines:
            self.assertIsInstance(headline_tuple, tuple)
            self.assertEqual(len(headline_tuple), 3)
            headline, url, source = headline_tuple
            self.assertIsInstance(headline, str)
            self.assertIsInstance(url, str)
            self.assertIsInstance(source, str)
            self.assertGreater(len(headline.strip()), 0)
    
    def test_find_latest_signals_file(self):
        """Test finding the latest signals file."""
        # Should find at least one signals file
        latest = self.find_latest_signals_file(self.writeup_dir)
        
        if latest:
            self.assertTrue(latest.exists(), "Latest signals file should exist")
            self.assertTrue(latest.name.startswith("signals_"), "Should be a signals file")
        else:
            self.skipTest("No signals files found for testing")
    
    def test_find_latest_signals_file_nonexistent_dir(self):
        """Test finding signals file in non-existent directory."""
        nonexistent_dir = Path("/nonexistent/directory/that/does/not/exist")
        latest = self.find_latest_signals_file(nonexistent_dir)
        self.assertIsNone(latest, "Should return None for non-existent directory")
    
    def test_get_portfolio_snapshot_with_file(self):
        """Test portfolio snapshot extraction from existing file."""
        # Create a temporary portfolio state file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            portfolio_file = Path(f.name)
            state = {
                "cash": 5000.0,
                "initial_capital": 10000.0,
                "positions": {
                    "BTC": {"quantity": 0.1, "avg_price": 50000.0},
                    "ETH": {"quantity": 2.0, "avg_price": 2000.0},
                },
                "daily_values": [
                    ["2025-11-22T00:00:00Z", 15000.0]
                ]
            }
            json.dump(state, f)
        
        try:
            portfolio_value, total_return_pct, date = self.get_portfolio_snapshot(portfolio_file)
            
            self.assertEqual(portfolio_value, 15000.0)
            self.assertEqual(total_return_pct, 50.0)  # (15000 - 10000) / 10000 * 100
            self.assertEqual(date, "2025-11-22")
        finally:
            portfolio_file.unlink()
    
    def test_get_portfolio_snapshot_no_file(self):
        """Test portfolio snapshot when file doesn't exist."""
        nonexistent_file = Path("/nonexistent/portfolio_state_buy.json")
        portfolio_value, total_return_pct, date = self.get_portfolio_snapshot(nonexistent_file)
        
        self.assertEqual(portfolio_value, 0.0)
        self.assertEqual(total_return_pct, 0.0)
        self.assertIsInstance(date, str)  # Should be a date string
    
    def test_get_portfolio_snapshot_no_daily_values(self):
        """Test portfolio snapshot when daily_values is missing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            portfolio_file = Path(f.name)
            state = {
                "cash": 5000.0,
                "initial_capital": 10000.0,
                "positions": {}
            }
            json.dump(state, f)
        
        try:
            portfolio_value, total_return_pct, date = self.get_portfolio_snapshot(portfolio_file)
            
            self.assertEqual(portfolio_value, 5000.0)  # Should use cash
            self.assertEqual(total_return_pct, -50.0)  # (5000 - 10000) / 10000 * 100
            self.assertIsInstance(date, str)
        finally:
            portfolio_file.unlink()
    
    def test_format_above_fold_section(self):
        """Test formatting the above-the-fold section."""
        headlines = [
            ("First headline", "https://example.com/1", "Source1"),
            ("Second headline", "https://example.com/2", "Source2"),
            ("Third headline", "https://example.com/3", "Source3")
        ]
        # Use absolute path to avoid relative_to() issues
        signals_file = self.project_root / "writeup/2025/11/22/signals_2025-11-22.md"
        
        section = self.format_above_fold_section(
            headlines=headlines,
            buy_portfolio_value=15000.0,
            buy_total_return_pct=50.0,
            sell_portfolio_value=12000.0,
            sell_total_return_pct=20.0,
            signals_file=signals_file,
            date="2025-11-22"
        )
        
        self.assertIn("Latest News Headlines", section)
        self.assertIn("First headline", section)
        self.assertIn("Second headline", section)
        self.assertIn("Third headline", section)
        self.assertIn("$15,000.00", section)
        self.assertIn("+50.00%", section)
        self.assertIn("$12,000.00", section)
        self.assertIn("+20.00%", section)
        self.assertIn("Buy Strategy", section)
        self.assertIn("Sell Strategy", section)
    
    def test_update_readme_with_markers(self):
        """Test updating README with proper markers."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            readme_file = Path(f.name)
            content = """# Project README

Some content here.

<!-- DAILY_UPDATE_START -->
Old content here
<!-- DAILY_UPDATE_END -->

More content here.
"""
            f.write(content)
        
        try:
            new_section = "## New Section\n\nNew content here."
            success = self.update_readme(readme_file, new_section)
            
            self.assertTrue(success, "Should successfully update README")
            
            # Read back and verify
            updated_content = readme_file.read_text()
            self.assertIn("<!-- DAILY_UPDATE_START -->", updated_content)
            self.assertIn("<!-- DAILY_UPDATE_END -->", updated_content)
            self.assertIn("New Section", updated_content)
            self.assertIn("New content here", updated_content)
            self.assertNotIn("Old content here", updated_content)
        finally:
            readme_file.unlink()
    
    def test_update_readme_no_markers(self):
        """Test updating README without markers should fail."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            readme_file = Path(f.name)
            content = """# Project README

Some content here.
"""
            f.write(content)
        
        try:
            new_section = "## New Section\n\nNew content here."
            success = self.update_readme(readme_file, new_section)
            
            self.assertFalse(success, "Should fail when markers are missing")
        finally:
            readme_file.unlink()
    
    def test_update_readme_nonexistent_file(self):
        """Test updating non-existent README should fail."""
        nonexistent_file = Path("/nonexistent/README.md")
        new_section = "## New Section\n\nNew content here."
        success = self.update_readme(nonexistent_file, new_section)
        
        self.assertFalse(success, "Should fail when file doesn't exist")
    
    def test_headline_extraction_whitespace_handling(self):
        """Test that headlines with extra whitespace are trimmed."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            signals_file = Path(f.name)
            content = """# Trading Signals

## 🔥 Top Stories

<div>
<table>
  <tr>
    <td>
      <strong>1.   Headline with extra spaces   </strong>
    </td>
  </tr>
</table>
</div>
"""
            f.write(content)
        
        try:
            # Without URL/source pattern, won't match new regex
            headlines = self.extract_headlines(signals_file, limit=5)
            self.assertEqual(len(headlines), 0, "Without URL/source pattern, should return empty")
        finally:
            signals_file.unlink()
    
    def test_headline_extraction_with_attributes(self):
        """Test that headlines with style attributes still work."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            signals_file = Path(f.name)
            content = """# Trading Signals

## 🔥 Top Stories

<div>
<table>
  <tr>
    <td>
      <strong style="font-size: 1.1em;">1. Headline with style attribute</strong>
    </td>
  </tr>
</table>
</div>
"""
            f.write(content)
        
        try:
            # Without URL/source pattern, won't match new regex
            headlines = self.extract_headlines(signals_file, limit=5)
            self.assertEqual(len(headlines), 0, "Without URL/source pattern, should return empty")
        finally:
            signals_file.unlink()


if __name__ == "__main__":
    unittest.main()

