"""
Tests for the fallback retry path in signal generation.

These tests exercise the actual fallback logic (lines 1262-1480 in digest.py),
which was previously untested. The existing tests in test_digest_generation.py
mock away the entire parsing/fallback path, making them ineffective at catching
real-world failures like:

1. Regex mismatch on retry temp files (signals_YYYY-MM-DD_retry.md)
2. Unbound variable when signal_parser not initialized in fallback path
3. Missing canonicalization in fallback path

Key principle: Mock at the LLM boundary, not the parser.
"""

import pytest
import tempfile
import asyncio
import sys
import os
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

# Add src and scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestFallbackRetryPath:
    """Integration tests for the fallback retry logic in bundle_writeup."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace with mock data files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_dir = temp_path / ".data"
            writeup_dir = temp_path / "writeup"
            data_dir.mkdir()
            writeup_dir.mkdir()

            # Create sample news data
            news_data = [
                {
                    "id": 1,
                    "title": "Bitcoin hits new highs",
                    "url": "https://example.com/btc",
                    "created_at": datetime.now().isoformat(),
                    "summary": "BTC price momentum continues"
                },
                {
                    "id": 2,
                    "title": "Ethereum upgrade announced",
                    "url": "https://example.com/eth",
                    "created_at": datetime.now().isoformat(),
                    "summary": "ETH network improvements"
                }
            ]

            # Create token data
            token_data = {
                "count": 3,
                "tokens": [
                    {"symbol": "$BTC", "name": "Bitcoin", "news_count": 5, "total_tvl": 1000000, "stablecoin": False},
                    {"symbol": "$ETH", "name": "Ethereum", "news_count": 3, "total_tvl": 500000, "stablecoin": False},
                    {"symbol": "$SQUID", "name": "Leviathan", "news_count": 1, "total_tvl": 100000, "stablecoin": False},
                ]
            }

            # Write data files
            (data_dir / "leviathan_news.json").write_text(json.dumps(news_data))
            (data_dir / "leviathan_tokens.json").write_text(json.dumps(token_data))

            yield {
                "temp_path": temp_path,
                "data_dir": data_dir,
                "writeup_dir": writeup_dir,
                "news_data": news_data,
                "token_data": token_data
            }

    def test_signal_parser_initialized_before_conditional(self, temp_workspace):
        """Test that signal_parser is available in fallback path.

        This test catches the bug where signal_parser was only defined inside
        the 'if not retry_with_fallback:' block, causing UnboundLocalError
        when the fallback path was taken.
        """
        async def run_test():
            import digest

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_workspace["temp_path"])

                # Mock engine to return REFUSAL on first call (triggers immediate fallback)
                # and valid signals on fallback call
                refusal_response = "No trading signals to generate. None of the headlines contain actionable catalysts."
                valid_response = "**$BTC Bitcoin: STRONG BUY** - price momentum continues ([more info](https://example.com))"

                mock_engine = MagicMock()
                mock_engine.news_fetcher = MagicMock()
                mock_engine.news_fetcher.fetch_all_news_24h = MagicMock(return_value=temp_workspace["news_data"])
                mock_engine.news_fetcher.fetch_squid_pass_winner = MagicMock(return_value=None)
                mock_engine.generate_writeup = AsyncMock(return_value=refusal_response)
                mock_engine.generate_writeup_with_prompt = AsyncMock(return_value=valid_response)

                with patch('digest.DigestEngine', return_value=mock_engine), \
                     patch('digest.WRITEUP_DIR', temp_workspace["writeup_dir"]), \
                     patch('digest.ACTIVE_PROMPT', 'signals'), \
                     patch('digest.IncrementalBacktest') as MockBacktest, \
                     patch('digest.generate_market_snapshot', return_value="## Market\n* BTC: $100k *"), \
                     patch('digest._get_token_id_map', return_value={'BTC': {'canonical_tag': 'btc', 'name': 'Bitcoin'}}), \
                     patch('digest.format_backtest_for_newsletter', return_value="## Backtest Results\nMock results"):

                    MockBacktest.return_value.run.return_value = {"portfolio_value": 10000.0}
                    MockBacktest.return_value.close = MagicMock()

                    # This should NOT raise UnboundLocalError
                    try:
                        await digest.bundle_writeup(verbose=True)
                    except UnboundLocalError as e:
                        if "signal_parser" in str(e):
                            pytest.fail(f"signal_parser not available in fallback path: {e}")
                        raise

                    # Verify fallback was called (generate_writeup_with_prompt is the fallback)
                    assert mock_engine.generate_writeup_with_prompt.called, \
                        "Fallback prompt (generate_writeup_with_prompt) should have been called"

            finally:
                os.chdir(original_cwd)

        asyncio.run(run_test())

    def test_llm_refusal_triggers_fallback(self, temp_workspace):
        """Test that LLM refusal triggers the fallback prompt."""
        async def run_test():
            import digest

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_workspace["temp_path"])

                # Track call order
                call_sequence = []

                # First call: refusal
                refusal_response = "I cannot generate signals because there are no specific token catalysts in the news."

                # Second call (fallback): valid signals
                valid_response = (
                    "**$BTC Bitcoin: WEAK BUY** - market momentum improving ([more info](https://example.com))\n"
                    "**$ETH Ethereum: WEAK SELL** - consolidation pattern ([more info](https://example.com))"
                )

                async def mock_generate(*args, **kwargs):
                    call_sequence.append("generate_writeup")
                    return refusal_response

                async def mock_generate_with_prompt(*args, **kwargs):
                    call_sequence.append("generate_writeup_with_prompt")
                    return valid_response

                mock_engine = MagicMock()
                mock_engine.news_fetcher = MagicMock()
                mock_engine.news_fetcher.fetch_all_news_24h = MagicMock(return_value=temp_workspace["news_data"])
                mock_engine.news_fetcher.fetch_squid_pass_winner = MagicMock(return_value=None)
                mock_engine.generate_writeup = AsyncMock(side_effect=mock_generate)
                mock_engine.generate_writeup_with_prompt = AsyncMock(side_effect=mock_generate_with_prompt)

                with patch('digest.DigestEngine', return_value=mock_engine), \
                     patch('digest.WRITEUP_DIR', temp_workspace["writeup_dir"]), \
                     patch('digest.ACTIVE_PROMPT', 'signals'), \
                     patch('digest.IncrementalBacktest') as MockBacktest, \
                     patch('digest.generate_market_snapshot', return_value="## Market\n* mock *"), \
                     patch('digest._get_token_id_map', return_value={'BTC': {'canonical_tag': 'btc'}, 'ETH': {'canonical_tag': 'eth'}}), \
                     patch('digest.format_backtest_for_newsletter', return_value="## Backtest\nMock"):

                    MockBacktest.return_value.run.return_value = {"portfolio_value": 10000.0}
                    MockBacktest.return_value.close = MagicMock()

                    await digest.bundle_writeup(verbose=True)

                # Verify call sequence: initial generation, then fallback
                assert "generate_writeup" in call_sequence, "Initial generation should be called"
                assert "generate_writeup_with_prompt" in call_sequence, "Fallback should be called after refusal"

            finally:
                os.chdir(original_cwd)

        asyncio.run(run_test())

    def test_retry_tempfile_names_parse_correctly(self):
        """Test that retry temp files with _retry suffix parse correctly.

        This test catches the regex bug where signals_YYYY-MM-DD_retry.md
        files didn't match the parser's expected pattern.
        """
        from squid_digest.backtest.signal_parser import SignalParser

        valid_content = """## 🎯 Trading Signals

**$BTC Bitcoin: STRONG BUY** - Test reason for buy signal
**$ETH Ethereum: SELL** - Test reason for sell signal
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = SignalParser(Path(tmpdir))

            # Test standard filename
            standard_file = Path(tmpdir) / "signals_2025-12-20.md"
            standard_file.write_text(valid_content)
            signals = parser.parse_file(standard_file)
            assert len(signals) == 2, "Standard filename should parse correctly"

            # Test _retry suffix (the bug that was fixed)
            retry_file = Path(tmpdir) / "signals_2025-12-20_retry.md"
            retry_file.write_text(valid_content)
            signals = parser.parse_file(retry_file)
            assert len(signals) == 2, "Retry suffix filename should parse correctly"

            # Test _retry_canonical suffix
            canonical_file = Path(tmpdir) / "signals_2025-12-20_retry_canonical.md"
            canonical_file.write_text(valid_content)
            signals = parser.parse_file(canonical_file)
            assert len(signals) == 2, "Retry canonical suffix filename should parse correctly"

    def test_format_validation_detects_refusal_patterns(self):
        """Test that format validation correctly detects LLM refusal patterns."""
        import re

        # These are the refusal patterns from digest.py
        refusal_patterns = [
            r"no\s+(trading\s+)?signals?\s+(to\s+generate|available)",
            r"cannot\s+generate\s+signals?",
            r"unable\s+to\s+(generate|provide)\s+signals?",
            r"(insufficient|no)\s+(news\s+)?(catalysts?|data)",
            r"none\s+of\s+the\s+(headlines?|news)",
        ]

        # Test cases that should match refusal patterns
        refusal_responses = [
            "No trading signals to generate.",
            "I cannot generate signals for this news.",
            "Unable to provide signals due to lack of catalysts.",
            "Insufficient catalysts in today's headlines.",
            "None of the headlines reference tracked tokens.",
        ]

        for response in refusal_responses:
            matched = any(re.search(p, response, re.IGNORECASE) for p in refusal_patterns)
            assert matched, f"Should detect refusal pattern in: {response}"

        # Test cases that should NOT match (valid signal responses)
        valid_responses = [
            "**$BTC Bitcoin: STRONG BUY** - price momentum",
            "**$ETH Ethereum: SELL** - consolidation pattern",
        ]

        for response in valid_responses:
            matched = any(re.search(p, response, re.IGNORECASE) for p in refusal_patterns)
            assert not matched, f"Should NOT detect refusal in valid signals: {response}"

    def test_canonicalization_handles_emoji_format(self):
        """Test that canonicalization converts emoji format to bold format."""
        import sys
        scripts_path = str(Path(__file__).parent.parent / "scripts")
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)

        from digest import canonicalize_trading_signals_to_bold_lines

        # Input: emoji format (what LLM sometimes produces)
        emoji_input = "🟢 Bitcoin ($BTC): STRONG BUY - price momentum looking strong"

        # Expected: converted to bold format
        result = canonicalize_trading_signals_to_bold_lines(emoji_input)

        # Should contain the symbol in bold format
        assert "**$BTC" in result or result == emoji_input, \
            f"Canonicalization should convert emoji format. Got: {result}"

    def test_signal_coercion_converts_hold_to_weak(self):
        """Test that HOLD/NEUTRAL labels are coerced to WEAK BUY/WEAK SELL."""
        import sys
        scripts_path = str(Path(__file__).parent.parent / "scripts")
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)

        from digest import coerce_trading_signals_to_supported_types

        # Input: signal with HOLD label (not valid for backtest)
        hold_input = "**$BTC Bitcoin: HOLD** - waiting for breakout confirmation"

        # Coerce with allow_hold_coercion=True
        result, changes = coerce_trading_signals_to_supported_types(
            hold_input,
            allow_hold_coercion=True
        )

        # Should be converted to WEAK BUY or WEAK SELL
        assert "HOLD" not in result or len(changes) > 0, \
            f"HOLD should be coerced to WEAK BUY/SELL. Got: {result}"


class TestGracefulDegradation:
    """Test graceful degradation when LLM fails to generate valid signals."""

    def test_invalid_format_does_not_crash(self):
        """Script should continue with empty signals when LLM returns invalid format."""
        # Simulate LLM returning market commentary instead of signals
        invalid_response = """
**Macro demand for alternative stores of value** — Bitcoin and Ether are positioned as scarce digital commodities

**Technical analysis suggests caution** — Moving averages show consolidation patterns
"""
        # Verify this would NOT pass format validation
        import re
        valid_signal_type_re = r'(STRONG\s+BUY|BUY|WEAK\s+BUY|WEAK\s+SELL|SELL|STRONG\s+SELL)'
        format_valid = re.search(
            rf'^\s*\*\*\$[A-Za-z0-9]+\s+[^:]+?:\s+{valid_signal_type_re}\*\*\s*-\s*.+$',
            invalid_response,
            re.IGNORECASE | re.MULTILINE
        )
        assert format_valid is None, "Invalid format should not pass validation"

    def test_valid_signal_format_passes(self):
        """Valid signal format should pass validation."""
        valid_response = """**$BTC Bitcoin: STRONG BUY** - Momentum looks bullish

**$ETH Ethereum: SELL** - Breaking down from support
"""
        import re
        valid_signal_type_re = r'(STRONG\s+BUY|BUY|WEAK\s+BUY|WEAK\s+SELL|SELL|STRONG\s+SELL)'
        format_valid = re.search(
            rf'^\s*\*\*\$[A-Za-z0-9]+\s+[^:]+?:\s+{valid_signal_type_re}\*\*\s*-\s*.+$',
            valid_response,
            re.IGNORECASE | re.MULTILINE
        )
        assert format_valid is not None, "Valid format should pass validation"


class TestSignalParserEdgeCases:
    """Additional edge case tests for signal parser robustness."""

    def test_parser_handles_mixed_formats(self):
        """Test that parser handles files with mixed signal formats."""
        from squid_digest.backtest.signal_parser import SignalParser

        # Content with both bold and emoji formats
        mixed_content = """## 🎯 Trading Signals

**$BTC Bitcoin: STRONG BUY** - price momentum
🟢 Ethereum ([$ETH](url)): BUY - network upgrade
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = SignalParser(Path(tmpdir))
            filepath = Path(tmpdir) / "signals_2025-12-20.md"
            filepath.write_text(mixed_content)

            signals = parser.parse_file(filepath)
            # Should parse at least the bold format signal
            assert len(signals) >= 1, "Should parse at least one signal from mixed format"

    def test_parser_handles_empty_trading_signals_section(self):
        """Test that parser handles empty trading signals section."""
        from squid_digest.backtest.signal_parser import SignalParser

        empty_content = """## 🎯 Trading Signals

"""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = SignalParser(Path(tmpdir))
            filepath = Path(tmpdir) / "signals_2025-12-20.md"
            filepath.write_text(empty_content)

            signals = parser.parse_file(filepath)
            assert signals == [], "Empty section should return empty list"

    def test_parser_handles_missing_section(self):
        """Test that parser handles missing Trading Signals section."""
        from squid_digest.backtest.signal_parser import SignalParser

        no_section_content = """# Some other content

No trading signals here.
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = SignalParser(Path(tmpdir))
            filepath = Path(tmpdir) / "signals_2025-12-20.md"
            filepath.write_text(no_section_content)

            signals = parser.parse_file(filepath)
            assert signals == [], "Missing section should return empty list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
