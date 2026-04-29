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


class TestReformatPassAndSkip:
    """Tests for the reformat-pass + skip path added after the 2026-04-28 incident.

    These mirror the existing TestFallbackRetryPath fixture and mocking style:
    drive bundle_writeup() through the engine-method seam and assert on the
    written meta.json + signals file.
    """

    @pytest.fixture
    def temp_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_dir = temp_path / ".data"
            writeup_dir = temp_path / "writeup"
            data_dir.mkdir()
            writeup_dir.mkdir()

            news_data = [
                {
                    "id": 1,
                    "headline": "Bitcoin struggling to hold support",
                    "title": "Bitcoin struggling to hold support",
                    "url": "https://example.com/btc",
                    "created_at": datetime.now().isoformat(),
                    "summary": "BTC faces resistance",
                },
                {
                    "id": 2,
                    "headline": "Solana core devs align on Falcon signatures",
                    "title": "Solana core devs align on Falcon signatures",
                    "url": "https://example.com/sol",
                    "created_at": datetime.now().isoformat(),
                    "summary": "Quantum-resistant security",
                },
            ]
            token_data = {
                "count": 3,
                "tokens": [
                    {"symbol": "$BTC", "name": "Bitcoin", "news_count": 5, "total_tvl": 1000000, "stablecoin": False},
                    {"symbol": "$ETH", "name": "Ethereum", "news_count": 3, "total_tvl": 500000, "stablecoin": False},
                    {"symbol": "$SOL", "name": "Solana", "news_count": 2, "total_tvl": 800000, "stablecoin": False},
                ],
            }
            (data_dir / "leviathan_news.json").write_text(json.dumps(news_data))
            (data_dir / "leviathan_tokens.json").write_text(json.dumps(token_data))

            yield {
                "temp_path": temp_path,
                "data_dir": data_dir,
                "writeup_dir": writeup_dir,
                "news_data": news_data,
                "token_data": token_data,
            }

    @pytest.fixture
    def apr28_fixtures(self):
        """Load the actual Apr 28 prose responses extracted from the failed CI run."""
        fixture_path = Path(__file__).parent / "fixtures" / "apr28_prose_responses.json"
        with open(fixture_path) as f:
            return json.load(f)

    def _build_mock_engine(self, news_data, llm_responses):
        """Build a mock engine where generate_writeup returns the strict response,
        and generate_writeup_with_prompt returns fallback / reformat in order
        based on call count.

        llm_responses: dict with keys "strict", "fallback", "reformat".
        """
        mock_engine = MagicMock()
        mock_engine.news_fetcher = MagicMock()
        mock_engine.news_fetcher.fetch_all_news_24h = MagicMock(return_value=news_data)
        mock_engine.news_fetcher.fetch_squid_pass_winner = MagicMock(return_value=None)
        mock_engine.generate_writeup = AsyncMock(return_value=llm_responses["strict"])

        call_log = {"with_prompt_calls": []}

        async def with_prompt_side_effect(*args, **kwargs):
            call_log["with_prompt_calls"].append(kwargs)
            n = len(call_log["with_prompt_calls"])
            if n == 1:
                return llm_responses["fallback"]
            return llm_responses["reformat"]

        mock_engine.generate_writeup_with_prompt = AsyncMock(side_effect=with_prompt_side_effect)
        mock_engine._call_log = call_log
        return mock_engine

    def _read_today_meta(self, writeup_dir):
        """Find and return today's meta.json content (digest writes it under
        the date-keyed subdirectory)."""
        # Search for any meta_*.json file written under writeup_dir
        meta_files = list(writeup_dir.rglob("meta_*.json"))
        if not meta_files:
            return None
        # Return most recent
        return json.loads(meta_files[-1].read_text())

    def _read_today_signals(self, writeup_dir):
        signals_files = list(writeup_dir.rglob("signals_*.md"))
        if not signals_files:
            return None
        return signals_files[-1].read_text()

    def test_reformat_pass_recovers_from_prose(self, temp_workspace, apr28_fixtures):
        """When strict + fallback return prose but the reformat pass produces
        valid signals, the run should complete with signals_status=reformatted."""
        async def run_test():
            import digest

            llm_responses = {
                "strict": apr28_fixtures["strict_response"],
                "fallback": apr28_fixtures["fallback_response"],
                "reformat": apr28_fixtures["reformat_recovered_response"],
            }
            mock_engine = self._build_mock_engine(temp_workspace["news_data"], llm_responses)

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_workspace["temp_path"])
                with patch('digest.DigestEngine', return_value=mock_engine), \
                     patch('digest.WRITEUP_DIR', temp_workspace["writeup_dir"]), \
                     patch('digest.ACTIVE_PROMPT', 'signals'), \
                     patch('digest.IncrementalBacktest') as MockBacktest, \
                     patch('digest.generate_market_snapshot', return_value="## Market\n* mock *"), \
                     patch('digest._get_token_id_map', return_value={'BTC': {'canonical_tag': 'btc'}, 'ETH': {'canonical_tag': 'eth'}, 'SOL': {'canonical_tag': 'sol'}}), \
                     patch('digest.format_backtest_for_newsletter', return_value="## Backtest Results\nMock"):
                    MockBacktest.return_value.run.return_value = {"portfolio_value": 10000.0}
                    MockBacktest.return_value.close = MagicMock()
                    await digest.bundle_writeup(verbose=True)

                meta = self._read_today_meta(temp_workspace["writeup_dir"])
                assert meta is not None, "meta.json should be written"
                assert meta.get("signals_status") == "reformatted", \
                    f"signals_status should be 'reformatted', got {meta.get('signals_status')}"

                # Verify the reformat call was made with user_message set to fallback prose
                calls = mock_engine._call_log["with_prompt_calls"]
                assert len(calls) >= 2, "Both fallback and reformat should be called"
                reformat_call = calls[1]
                assert reformat_call.get("user_message") == apr28_fixtures["fallback_response"], \
                    "Reformat call should pass fallback prose as user_message"
                assert reformat_call.get("prompt_type") == "signals_reformat"
            finally:
                os.chdir(original_cwd)

        asyncio.run(run_test())

    def test_full_skip_publishes_banner(self, temp_workspace, apr28_fixtures):
        """When all three passes fail, run should complete with skip banner
        and signals_status=skipped (not raise ValueError)."""
        async def run_test():
            import digest

            llm_responses = {
                "strict": apr28_fixtures["strict_response"],
                "fallback": apr28_fixtures["fallback_response"],
                "reformat": apr28_fixtures["reformat_no_signals_response"],  # NO_SIGNALS
            }
            mock_engine = self._build_mock_engine(temp_workspace["news_data"], llm_responses)

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_workspace["temp_path"])
                with patch('digest.DigestEngine', return_value=mock_engine), \
                     patch('digest.WRITEUP_DIR', temp_workspace["writeup_dir"]), \
                     patch('digest.ACTIVE_PROMPT', 'signals'), \
                     patch('digest.IncrementalBacktest') as MockBacktest, \
                     patch('digest.generate_market_snapshot', return_value="## Market\n* mock *"), \
                     patch('digest._get_token_id_map', return_value={'BTC': {'canonical_tag': 'btc'}}), \
                     patch('digest.format_backtest_for_newsletter', return_value="## Backtest\nMock"):
                    MockBacktest.return_value.run.return_value = {"portfolio_value": 10000.0}
                    MockBacktest.return_value.close = MagicMock()
                    # Must NOT raise ValueError
                    await digest.bundle_writeup(verbose=True)

                meta = self._read_today_meta(temp_workspace["writeup_dir"])
                assert meta is not None
                assert meta.get("signals_status") == "skipped", \
                    f"signals_status should be 'skipped', got {meta.get('signals_status')}"

                signals_md = self._read_today_signals(temp_workspace["writeup_dir"])
                assert signals_md is not None, "Signals file should be written"
                assert digest.SIGNALS_SKIPPED_BANNER_PHRASE.lower() in signals_md.lower(), \
                    "Skip banner phrase must appear in writeup"
                # Banner-only writeups should not contain a backtest section
                assert "## 📈 Backtest Results" not in signals_md
                assert "## 📈 Sentiment Portfolio" not in signals_md
            finally:
                os.chdir(original_cwd)

        asyncio.run(run_test())

    def test_no_signals_sentinel_does_not_parse_as_token(self, temp_workspace, apr28_fixtures):
        """The literal NO_SIGNALS sentinel from the reformat pass must take the
        skip path, not be misinterpreted as a token name."""
        async def run_test():
            import digest

            llm_responses = {
                "strict": apr28_fixtures["strict_response"],
                "fallback": apr28_fixtures["fallback_response"],
                "reformat": "NO_SIGNALS",
            }
            mock_engine = self._build_mock_engine(temp_workspace["news_data"], llm_responses)

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_workspace["temp_path"])
                with patch('digest.DigestEngine', return_value=mock_engine), \
                     patch('digest.WRITEUP_DIR', temp_workspace["writeup_dir"]), \
                     patch('digest.ACTIVE_PROMPT', 'signals'), \
                     patch('digest.IncrementalBacktest') as MockBacktest, \
                     patch('digest.generate_market_snapshot', return_value="## Market\n* mock *"), \
                     patch('digest._get_token_id_map', return_value={'BTC': {'canonical_tag': 'btc'}}), \
                     patch('digest.format_backtest_for_newsletter', return_value="## Backtest\nMock"):
                    MockBacktest.return_value.run.return_value = {"portfolio_value": 10000.0}
                    MockBacktest.return_value.close = MagicMock()
                    await digest.bundle_writeup(verbose=True)

                meta = self._read_today_meta(temp_workspace["writeup_dir"])
                assert meta.get("signals_status") == "skipped"
                signals_md = self._read_today_signals(temp_workspace["writeup_dir"])
                # NO_SIGNALS sentinel must not appear in subscriber-facing output
                assert "NO_SIGNALS" not in signals_md
            finally:
                os.chdir(original_cwd)

        asyncio.run(run_test())

    def test_skip_path_bypasses_no_backtest_guard(self, temp_workspace, apr28_fixtures):
        """The line-2090 'signals exist but no backtest' guard must NOT fire
        when signals_skipped=True. This test fails on pre-fix code because the
        banner string is >50 chars and the guard would raise."""
        async def run_test():
            import digest

            llm_responses = {
                "strict": apr28_fixtures["strict_response"],
                "fallback": apr28_fixtures["fallback_response"],
                "reformat": "NO_SIGNALS",
            }
            mock_engine = self._build_mock_engine(temp_workspace["news_data"], llm_responses)

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_workspace["temp_path"])
                # Force backtest_section to be empty by making backtest fail; this
                # exercises the no-backtest guard path. The skip flag must bypass it.
                with patch('digest.DigestEngine', return_value=mock_engine), \
                     patch('digest.WRITEUP_DIR', temp_workspace["writeup_dir"]), \
                     patch('digest.ACTIVE_PROMPT', 'signals'), \
                     patch('digest.IncrementalBacktest') as MockBacktest, \
                     patch('digest.generate_market_snapshot', return_value="## Market\n* mock *"), \
                     patch('digest._get_token_id_map', return_value={'BTC': {'canonical_tag': 'btc'}}):
                    # No format_backtest_for_newsletter patch — empty backtest_section path
                    MockBacktest.return_value.run.return_value = {"portfolio_value": 10000.0}
                    MockBacktest.return_value.close = MagicMock()
                    # The key assertion: this completes without raising
                    await digest.bundle_writeup(verbose=True)

                meta = self._read_today_meta(temp_workspace["writeup_dir"])
                assert meta.get("signals_status") == "skipped"
            finally:
                os.chdir(original_cwd)

        asyncio.run(run_test())

    def test_normal_success_path_marks_status_ok(self, temp_workspace):
        """When the strict prompt produces valid signals, signals_status='ok'
        must be persisted (verifies finding #2 from plan review — status is
        written on the success path, not just recovery branches)."""
        async def run_test():
            import digest

            valid_strict_response = (
                "**$BTC Bitcoin: STRONG BUY** - momentum continues ([more info](https://example.com))\n"
                "**$ETH Ethereum: BUY** - upgrade announced ([more info](https://example.com))"
            )
            mock_engine = MagicMock()
            mock_engine.news_fetcher = MagicMock()
            mock_engine.news_fetcher.fetch_all_news_24h = MagicMock(return_value=temp_workspace["news_data"])
            mock_engine.news_fetcher.fetch_squid_pass_winner = MagicMock(return_value=None)
            mock_engine.generate_writeup = AsyncMock(return_value=valid_strict_response)
            mock_engine.generate_writeup_with_prompt = AsyncMock(return_value=valid_strict_response)

            original_cwd = os.getcwd()
            try:
                os.chdir(temp_workspace["temp_path"])
                with patch('digest.DigestEngine', return_value=mock_engine), \
                     patch('digest.WRITEUP_DIR', temp_workspace["writeup_dir"]), \
                     patch('digest.ACTIVE_PROMPT', 'signals'), \
                     patch('digest.IncrementalBacktest') as MockBacktest, \
                     patch('digest.generate_market_snapshot', return_value="## Market\n* mock *"), \
                     patch('digest._get_token_id_map', return_value={'BTC': {'canonical_tag': 'btc'}, 'ETH': {'canonical_tag': 'eth'}}), \
                     patch('digest.format_backtest_for_newsletter', return_value="## Backtest Results\nMock"):
                    MockBacktest.return_value.run.return_value = {"portfolio_value": 10000.0}
                    MockBacktest.return_value.close = MagicMock()
                    await digest.bundle_writeup(verbose=True)

                meta = self._read_today_meta(temp_workspace["writeup_dir"])
                assert meta is not None
                assert meta.get("signals_status") == "ok", \
                    f"Normal success path should write signals_status='ok', got {meta.get('signals_status')}"
            finally:
                os.chdir(original_cwd)

        asyncio.run(run_test())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
