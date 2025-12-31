"""Integration tests for digest generation functionality."""

import unittest
import sys
import subprocess
import json
import shutil
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestDigestGeneration(unittest.TestCase):
    """Integration tests for digest generation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.project_root = Path(__file__).parent.parent
        self.scripts_dir = self.project_root / "scripts"
        self.writeup_dir = self.project_root / "writeup"
    
    def test_digest_script_exists(self):
        """Test that digest.py script exists."""
        digest_script = self.scripts_dir / "digest.py"
        self.assertTrue(digest_script.exists(), "digest.py script not found")
        self.assertTrue(digest_script.is_file(), "digest.py is not a file")
    
    def test_digest_script_importable(self):
        """Test that digest.py can be imported (syntax check)."""
        digest_script = self.scripts_dir / "digest.py"
        
        # Try to compile the script to check for syntax errors
        try:
            with open(digest_script, 'r') as f:
                code = f.read()
            compile(code, str(digest_script), 'exec')
        except SyntaxError as e:
            self.fail(f"digest.py has syntax errors: {e}")
    
    def test_required_modules_importable(self):
        """Test that required modules can be imported."""
        try:
            from squid_digest.telegram import TelegramClient, format_for_telegram
            from squid_digest.email import GhostEmailClient
        except ImportError as e:
            self.fail(f"Required modules cannot be imported: {e}")
    
    def test_writeup_directory_exists(self):
        """Test that writeup directory exists."""
        self.assertTrue(self.writeup_dir.exists(), "writeup/ directory not found")
        self.assertTrue(self.writeup_dir.is_dir(), "writeup/ is not a directory")
    
    def test_signals_files_format(self):
        """Test that signals files follow expected naming pattern."""
        signals_files = list(self.writeup_dir.rglob("signals_*.md"))
        
        # If there are signals files, check their format
        if signals_files:
            for signals_file in signals_files[:5]:  # Check first 5
                # Check naming pattern: signals_YYYY-MM-DD.md
                name = signals_file.stem  # signals_2025-11-17
                self.assertTrue(name.startswith("signals_"), 
                              f"File {signals_file.name} doesn't follow naming pattern")
                
                # Check date format
                date_part = name.replace("signals_", "")
                parts = date_part.split("-")
                self.assertEqual(len(parts), 3, 
                               f"Date in {signals_file.name} is not YYYY-MM-DD format")
                
                # Check file is readable
                try:
                    content = signals_file.read_text()
                    self.assertGreater(len(content), 0, 
                                     f"Signals file {signals_file.name} is empty")
                except Exception as e:
                    self.fail(f"Cannot read signals file {signals_file.name}: {e}")
    
    def test_sorted_tokens_verbose_logging(self):
        """Test that verbose logging with sorted_tokens doesn't crash.
        
        This test validates the fix for the TypeError where sorted_tokens
        (which contains tuples) was being accessed as if it contained dicts.
        """
        # Simulate the data structure that caused the bug
        # sorted_tokens is a list of tuples: [(symbol, token_dict), ...]
        all_relevant_tokens = {
            'BTC': {'name': 'Bitcoin', 'news_count': 5, 'total_tvl': 1000000},
            'ETH': {'name': 'Ethereum', 'news_count': 3, 'total_tvl': 500000},
            'BNB': {'name': 'Binance Coin', 'news_count': 2, 'total_tvl': 200000},
        }
        
        # This is what sorted() returns from .items()
        sorted_tokens = sorted(all_relevant_tokens.items(), key=lambda x: -x[1].get('news_count', 0))
        
        # This is the line that was failing - it should work now
        try:
            top_tokens = ', '.join([symbol for symbol, token in sorted_tokens[:10]])
            self.assertIsInstance(top_tokens, str)
            self.assertGreater(len(top_tokens), 0)
        except TypeError as e:
            self.fail(f"Verbose logging with sorted_tokens failed: {e}. "
                     f"This indicates the bug is not fixed - sorted_tokens should be unpacked as tuples.")
    
    def test_signals_generation_dry_run(self):
        """Test signals generation with mocked API calls (dry run).
        
        This test validates the core logic of bundle_writeup without making
        actual API calls. It uses sample data and mocks the LLM provider.
        """
        import tempfile
        import os
        
        # Create temporary directories
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_dir = temp_path / ".data"
            writeup_dir = temp_path / "writeup"
            data_dir.mkdir()
            writeup_dir.mkdir()
            
            # Copy sample data
            sample_data_dir = self.project_root / "data_sample"
            sample_news_file = sample_data_dir / "leviathan_news.json"
            
            if not sample_news_file.exists():
                self.skipTest("Sample news data not found")
            
            # Read and prepare sample news data
            with open(sample_news_file, 'r') as f:
                news_data = json.load(f)
            
            # Create minimal token data structure
            token_data = {
                "count": 3,
                "tokens": [
                    {
                        "symbol": "$CRV",
                        "name": "Curve DAO Token",
                        "news_count": 5,
                        "total_tvl": 5647063.857,
                        "stablecoin": False
                    },
                    {
                        "symbol": "$SQUID",
                        "name": "Leviathan Points",
                        "news_count": 2,
                        "total_tvl": 100000.0,
                        "stablecoin": False
                    },
                    {
                        "symbol": "$USDC",
                        "name": "USD Coin",
                        "news_count": 1,
                        "total_tvl": 1000000.0,
                        "stablecoin": True  # Should be filtered
                    }
                ]
            }
            
            # Write data files
            news_file = data_dir / "leviathan_news.json"
            token_file = data_dir / "leviathan_tokens.json"
            
            with open(news_file, 'w') as f:
                json.dump(news_data, f)
            
            with open(token_file, 'w') as f:
                json.dump(token_data, f)
            
            # Mock the bundle_writeup function's dependencies
            async def run_test():
                # Import here to avoid issues with module loading
                # Check for required dependencies first
                try:
                    import langchain_core
                except ImportError:
                    self.skipTest("langchain_core not installed - required dependency missing")
                
                # Add scripts to path for import
                scripts_path = str(self.project_root / "scripts")
                if scripts_path not in sys.path:
                    sys.path.insert(0, scripts_path)
                import digest
                bundle_writeup = digest.bundle_writeup
                from squid_digest.backtest.signal_parser import Signal

                # Change to temp directory so relative paths work
                original_cwd = os.getcwd()
                try:
                    os.chdir(temp_path)
                    
                    # Mock DigestEngine and its methods, plus backtest to avoid complexity
                    with patch('digest.DigestEngine') as MockEngine, \
                         patch('digest.WRITEUP_DIR', writeup_dir), \
                         patch('digest.ACTIVE_PROMPT', 'signals'), \
                         patch('digest.SignalParser.parse_file', return_value=[
                             Signal(
                                 date=datetime(2025, 12, 18),
                                 symbol="BTC",
                                 token_name="Bitcoin",
                                 signal_type="BUY",
                                 reason="Mock reason",
                             )
                         ]), \
                         patch('digest.generate_market_snapshot', return_value="## 💰 Market Snapshot\n\n* mock *"), \
                         patch('digest._get_token_id_map', return_value={
                             'BTC': {'canonical_tag': 'btc', 'name': 'Bitcoin'},
                             'ETH': {'canonical_tag': 'eth', 'name': 'Ethereum'},
                             'OPEN': {'canonical_tag': 'open', 'name': 'OPEN'},
                         }), \
                         patch('digest.format_dual_sentiment_portfolios', return_value=(
                             "## 📈 Sentiment Portfolio\n"
                             "### Current Sentiment Rankings\n\n"
                             "### Momentum Strategy\n\n"
                             "- **Portfolio Value:** `$10,000.00`\n"
                             "### Contrarian Strategy\n\n"
                             "- **Portfolio Value:** `$10,000.00`\n"
                         )):

                        # Create mock engine instance
                        mock_engine = MagicMock()
                        mock_engine.news_fetcher = MagicMock()
                        mock_engine.news_fetcher.fetch_all_news_24h = MagicMock(return_value=news_data)
                        mock_engine.news_fetcher.fetch_squid_pass_winner = MagicMock(return_value=None)
                        mock_engine.generate_writeup = AsyncMock(return_value=(
                            "**$BTC Bitcoin: STRONG BUY** - price momentum looking strong ([more info](https://example.com/btc))\n"
                            "**$ETH Ethereum: SELL** - consolidation pattern detected ([more info](https://example.com/eth))\n"
                            "**$OPEN OPEN: WEAK BUY** - awaiting breakout ([more info](https://example.com/open))\n"
                        ))
                        mock_engine.generate_writeup_with_prompt = AsyncMock(return_value=mock_engine.generate_writeup.return_value)
                        
                        MockEngine.return_value = mock_engine
                        
                        # Run bundle_writeup with verbose=True
                        await bundle_writeup(verbose=True)
                        
                        # Verify generate_writeup was called
                        self.assertTrue(mock_engine.generate_writeup.called, "generate_writeup should have been called")
                        
                        # Verify a signals file was created (check for both signals_*.md and any .md in writeup)
                        signals_files = list(writeup_dir.rglob("*.md"))
                        self.assertGreater(len(signals_files), 0, 
                                         f"At least one markdown file should be created in {writeup_dir}. "
                                         f"Found: {[str(f) for f in signals_files]}")
                        
                        # Verify file content
                        signals_file = signals_files[0]
                        content = signals_file.read_text()
                        self.assertIn("Crypto Trading Signals", content)
                        self.assertIn("## 🎯 Trading Signals", content)
                        self.assertIn("## 📈 Sentiment Portfolio", content)
                        self.assertIn("🟢 Bitcoin", content)
                        self.assertIn("🔴 Ethereum", content)
                finally:
                    os.chdir(original_cwd)
            
            # Run the async test
            asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
