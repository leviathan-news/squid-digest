"""
Tests for signal generation validation and error handling.

These tests ensure that:
1. Empty signal sections are detected and reported as errors
2. Signal validation catches missing or malformed signals
3. Integration tests ensure signal generation produces valid output
"""

import pytest
import tempfile
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSignalOutputValidation:
    """Test the signal output validation script."""

    def test_validate_signals_file_with_valid_signals(self):
        """Test validation passes with valid trading signals."""
        from scripts.validate_signals_output import validate_signals_file

        valid_content = """# Crypto Trading Signals

## 🎯 Trading Signals

🟢 Bitcoin ([$BTC](https://leviathannews.xyz/t/BTC)): STRONG BUY - Regulatory clarity expected
🟡 Ethereum ([$ETH](https://leviathannews.xyz/t/ETH)): WEAK BUY - Network upgrade momentum
🔴 Solana ([$SOL](https://leviathannews.xyz/t/SOL)): SELL - Validator concerns

## 📈 Sentiment Portfolio

### Sentiment Rankings
| Token | Score |
|-------|-------|
| BTC | +3.0 |

### Momentum Strategy

- **Portfolio Value:** `$10,500.00`

### Contrarian Strategy

- **Portfolio Value:** `$9,800.00`

---
*Disclaimer*
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(valid_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            is_valid, message = validate_signals_file(temp_path)
            assert is_valid, f"Valid signals should pass validation. Message: {message}"
            assert "3 valid signals" in message or "valid signals found" in message
        finally:
            temp_path.unlink()

    def test_validate_signals_file_with_empty_signals_section(self):
        """Test validation fails when signals section is empty."""
        from scripts.validate_signals_output import validate_signals_file

        empty_signals_content = """# Crypto Trading Signals

## 🎯 Trading Signals


---
*Disclaimer*
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(empty_signals_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            is_valid, message = validate_signals_file(temp_path)
            assert not is_valid, "Empty signals section should fail validation"
            # May fail with "empty or too short" or "No trading signals found"
            assert "empty" in message.lower() or "no trading signals" in message.lower()
        finally:
            temp_path.unlink()

    def test_validate_signals_file_missing_signals_header(self):
        """Test validation fails when signals header is missing."""
        from scripts.validate_signals_output import validate_signals_file

        no_header_content = """# Crypto Trading Signals

Some content but no trading signals section

---
*Disclaimer*
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(no_header_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            is_valid, message = validate_signals_file(temp_path)
            assert not is_valid, "Missing signals header should fail validation"
            assert "Trading signals section not found" in message
        finally:
            temp_path.unlink()

    def test_validate_signals_file_missing_signal_emojis(self):
        """Test validation fails when signal lines don't have emoji markers."""
        from scripts.validate_signals_output import validate_signals_file

        no_emoji_content = """# Crypto Trading Signals

## 🎯 Trading Signals

Bitcoin: STRONG BUY - Some reason
Ethereum: WEAK BUY - Another reason

---
*Disclaimer*
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(no_emoji_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            is_valid, message = validate_signals_file(temp_path)
            assert not is_valid, "Missing signal emojis should fail validation"
            assert "No trading signals found" in message or "emoji markers" in message
        finally:
            temp_path.unlink()

    def test_validate_signals_file_nonexistent_file(self):
        """Test validation fails gracefully for nonexistent files."""
        from scripts.validate_signals_output import validate_signals_file

        nonexistent_path = Path("/tmp/nonexistent_signals_test_12345.md")
        is_valid, message = validate_signals_file(nonexistent_path)
        assert not is_valid, "Nonexistent file should fail validation"
        assert "does not exist" in message

    def test_validate_signals_file_empty_file(self):
        """Test validation fails for empty files."""
        from scripts.validate_signals_output import validate_signals_file

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            # Write nothing (empty file)
            f.flush()
            temp_path = Path(f.name)

        try:
            is_valid, message = validate_signals_file(temp_path)
            assert not is_valid, "Empty file should fail validation"
            assert "empty" in message.lower()
        finally:
            temp_path.unlink()

    def test_validate_signals_file_multiple_signals(self):
        """Test validation with multiple valid signals."""
        from scripts.validate_signals_output import validate_signals_file

        multi_signal_content = """# Crypto Trading Signals

## 💰 Market Snapshot

[market data here]

## 🎯 Trading Signals

🟢 Bitcoin ([$BTC](url)): STRONG BUY - Reason 1
🟢 Ethereum ([$ETH](url)): BUY - Reason 2
🟡 Cardano ([$ADA](url)): WEAK BUY - Reason 3
🟠 Ripple ([$XRP](url)): WEAK SELL - Reason 4
🔴 Dogecoin ([$DOGE](url)): SELL - Reason 5

## 📈 Sentiment Portfolio

### Sentiment Rankings
| Token | Score |
|-------|-------|
| BTC | +3.0 |

### Momentum Strategy

- **Portfolio Value:** `$10,500.00`

### Contrarian Strategy

- **Portfolio Value:** `$9,800.00`

---
*Disclaimer*
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(multi_signal_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            is_valid, message = validate_signals_file(temp_path)
            assert is_valid, f"Multiple valid signals should pass. Message: {message}"
            assert "5 valid signals" in message or "valid signals found" in message
        finally:
            temp_path.unlink()


class TestSignalGenerationValidation:
    """Test validation during signal generation process."""

    def test_zero_signals_detection(self):
        """Test that zero signals with available data triggers error or retry.

        Regression test for 2025-11-27 failure where LLM generated zero signals
        due to strict prompt rules despite having valid news and token data.

        Expected behavior:
        1. First attempt with strict prompt may produce zero signals
        2. If zero signals detected, system retries with fallback (more inclusive) prompt
        3. If fallback produces signals, use them (success)
        4. If both fail, raise ValueError with diagnostic info
        """
        pytest.skip("Integration test - requires LLM mocking")

    def test_malformed_llm_response_detection(self):
        """Test that malformed LLM responses are caught."""
        pytest.skip("Integration test - requires LLM mocking")

    def test_empty_llm_response_rejection(self):
        """Test that empty LLM responses are rejected with diagnostic info."""
        pytest.skip("Integration test - requires LLM mocking")

    def test_wrong_format_llm_response_rejection(self):
        """Test that LLM responses in wrong format are rejected.

        Regression test for 2025-11-29 failure where LLM output emojis
        instead of the expected **$SYMBOL Token: SIGNAL** format.

        Expected behavior:
        1. LLM generates signals in wrong format (e.g., with emojis)
        2. Format validation detects mismatch and rejects response
        3. ValueError is raised with diagnostic info
        4. Diagnostic file is saved for debugging
        """
        pytest.skip("Integration test - requires LLM mocking")


class TestBacktestValidation:
    """Test backtest section validation."""

    def test_missing_backtest_section_detected(self):
        """Test that missing backtest sections are caught.

        Regression test for 2025-11-29 where signals were present but
        backtest section was missing due to parsing failure.
        """
        from scripts.validate_signals_output import validate_signals_file

        # Content with signals but NO backtest section
        signals_without_backtest = """# Crypto Trading Signals

## 💰 Market Snapshot

Some market data

## 🎯 Trading Signals

🟢 Bitcoin (<a href="url">$BTC</a>): STRONG BUY - Reason 1
🟢 Ethereum (<a href="url">$ETH</a>): BUY - Reason 2

---
*Disclaimer*
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(signals_without_backtest)
            f.flush()
            temp_path = Path(f.name)

        try:
            is_valid, message = validate_signals_file(temp_path)
            assert not is_valid, "Signals without backtest should fail validation"
            assert "portfolio section is missing" in message.lower()
            assert "2 signals" in message  # Should detect 2 signals
        finally:
            temp_path.unlink()

    def test_backtest_section_present_passes(self):
        """Test that files with proper backtest sections pass validation."""
        from scripts.validate_signals_output import validate_signals_file

        complete_signals_file = """# Crypto Trading Signals

## 💰 Market Snapshot

Some market data

## 🎯 Trading Signals

🟢 Bitcoin (<a href="url">$BTC</a>): STRONG BUY - Reason 1
🟢 Ethereum (<a href="url">$ETH</a>): BUY - Reason 2

## 📈 Backtest Results
### Buy the News Strategy

*How would a portfolio perform if it traded daily on Leviathan News headlines?*

- **Portfolio Value:** `$11,454.13`
- **Total Return:** +14.54%

### Sell the News Strategy

*How would a portfolio perform if it traded daily on Leviathan News headlines?*

- **Portfolio Value:** `$8,123.45`
- **Total Return:** -18.77%

---
*Disclaimer*
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(complete_signals_file)
            f.flush()
            temp_path = Path(f.name)

        try:
            is_valid, message = validate_signals_file(temp_path)
            assert is_valid, f"Complete signals file should pass. Message: {message}"
            assert "2 valid signals" in message
            assert "portfolio section present" in message
        finally:
            temp_path.unlink()

    def test_sentiment_portfolio_format_passes(self):
        """Test that new sentiment portfolio format passes validation."""
        from scripts.validate_signals_output import validate_signals_file

        sentiment_format_content = """# Crypto Trading Signals

## 💰 Market Snapshot

Some market data

## 🎯 Trading Signals

🟢 Bitcoin (<a href="url">$BTC</a>): STRONG BUY - Reason 1
🟢 Ethereum (<a href="url">$ETH</a>): BUY - Reason 2

## 📈 Sentiment Portfolio

### Current Sentiment Rankings

| Token | Sentiment | Trend |
|-------|-----------|-------|
| BTC   | +4.2      | ↑     |
| ETH   | +2.1      | ↓     |

### Momentum Strategy

*Long top sentiment, short bottom sentiment*

- **Portfolio Value:** `$12,450.00`
- **Total Return:** +24.5%

### Contrarian Strategy

*Long bottom sentiment, short top sentiment*

- **Portfolio Value:** `$9,500.00`
- **Total Return:** -5.0%

---
*Disclaimer*
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(sentiment_format_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            is_valid, message = validate_signals_file(temp_path)
            assert is_valid, f"Sentiment portfolio format should pass. Message: {message}"
            assert "2 valid signals" in message
        finally:
            temp_path.unlink()

    def test_incomplete_backtest_section_detected(self):
        """Test that incomplete backtest sections are caught."""
        from scripts.validate_signals_output import validate_signals_file

        signals_with_incomplete_backtest = """# Crypto Trading Signals

## 🎯 Trading Signals

🟢 Bitcoin (<a href="url">$BTC</a>): STRONG BUY - Reason 1

## 📈 Backtest Results

Just a header, no real content.

---
*Disclaimer*
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(signals_with_incomplete_backtest)
            f.flush()
            temp_path = Path(f.name)

        try:
            is_valid, message = validate_signals_file(temp_path)
            assert not is_valid, "Incomplete backtest should fail validation"
            assert "missing required content" in message.lower() or "too short" in message.lower()
        finally:
            temp_path.unlink()


class TestSignalParserRobustness:
    """Test that signal parser handles edge cases."""

    def test_signal_parser_handles_multiple_signals_per_line(self):
        """Test that parser correctly splits multiple signals on one line."""
        pytest.skip("Integration test - requires parser instantiation")

    def test_signal_parser_handles_varied_emoji_types(self):
        """Test that parser recognizes all signal emoji types."""
        pytest.skip("Integration test - requires parser instantiation")

    def test_signal_parser_ignores_non_signal_content(self):
        """Test that parser filters out non-signal sections."""
        pytest.skip("Integration test - requires parser instantiation")


class TestSignalParserFilenamePatterns:
    """Test that signal parser handles various filename patterns including retry suffixes.

    This tests the fix for a bug where temp files with _retry or _retry_canonical
    suffixes (e.g., signals_2025-12-20_retry.md) failed to parse because the
    filename regex didn't extract the date correctly.
    """

    def test_parse_standard_signals_filename(self):
        """Test that standard signals_YYYY-MM-DD.md files are parsed correctly."""
        from squid_digest.backtest.signal_parser import SignalParser

        valid_content = """## 🎯 Trading Signals

**$BTC Bitcoin: STRONG BUY** - Test reason for buy signal
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = SignalParser(Path(tmpdir))
            filepath = Path(tmpdir) / "signals_2025-12-20.md"
            filepath.write_text(valid_content)

            signals = parser.parse_file(filepath)
            assert len(signals) == 1
            assert signals[0].symbol == "BTC"
            assert signals[0].signal_type == "STRONG BUY"

    def test_parse_retry_suffix_filename(self):
        """Test that signals_YYYY-MM-DD_retry.md files are parsed correctly.

        This is the primary bug fix - retry temp files were failing to parse.
        """
        from squid_digest.backtest.signal_parser import SignalParser

        valid_content = """## 🎯 Trading Signals

**$ETH Ethereum: BUY** - Test reason for ETH buy signal
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = SignalParser(Path(tmpdir))
            filepath = Path(tmpdir) / "signals_2025-12-20_retry.md"
            filepath.write_text(valid_content)

            signals = parser.parse_file(filepath)
            assert len(signals) == 1, "Retry suffix filename should parse correctly"
            assert signals[0].symbol == "ETH"
            assert signals[0].signal_type == "BUY"

    def test_parse_retry_canonical_suffix_filename(self):
        """Test that signals_YYYY-MM-DD_retry_canonical.md files are parsed correctly."""
        from squid_digest.backtest.signal_parser import SignalParser

        valid_content = """## 🎯 Trading Signals

**$SOL Solana: WEAK SELL** - Test reason for SOL signal
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = SignalParser(Path(tmpdir))
            filepath = Path(tmpdir) / "signals_2025-12-20_retry_canonical.md"
            filepath.write_text(valid_content)

            signals = parser.parse_file(filepath)
            assert len(signals) == 1, "Retry canonical suffix filename should parse correctly"
            assert signals[0].symbol == "SOL"
            assert signals[0].signal_type == "WEAK SELL"

    def test_parse_digest_prefix_with_suffix(self):
        """Test that digest_YYYY-MM-DD_suffix.md files are parsed correctly."""
        from squid_digest.backtest.signal_parser import SignalParser

        valid_content = """## 🎯 Trading Signals

**$AAVE Aave: SELL** - Test reason
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = SignalParser(Path(tmpdir))
            filepath = Path(tmpdir) / "digest_2025-12-20_test.md"
            filepath.write_text(valid_content)

            signals = parser.parse_file(filepath)
            assert len(signals) == 1
            assert signals[0].symbol == "AAVE"


class TestSkipModeValidation:
    """Tests for the --meta skip-mode added to scripts/validate_signals_output.py.

    When meta records signals_status='skipped', the validator runs a relaxed
    branch that confirms the subscriber-facing skip banner is present and
    skips the emoji-line + portfolio-section requirements.
    """

    def _write_pair(self, tmpdir, signals_content, meta_dict):
        """Write a signals.md and meta.json pair into tmpdir, return their paths."""
        import json as _json
        signals_path = Path(tmpdir) / "signals_2026-04-28.md"
        meta_path = Path(tmpdir) / "meta_2026-04-28.json"
        signals_path.write_text(signals_content)
        meta_path.write_text(_json.dumps(meta_dict))
        return signals_path, meta_path

    def test_skip_mode_passes_with_banner_and_status(self):
        """meta.signals_status='skipped' + banner present → validator returns True."""
        from scripts.validate_signals_output import validate_signals_file, SIGNALS_SKIPPED_BANNER_PHRASE

        skipped_content = f"""# Crypto Trading Signals - April 28, 2026

## 🎯 Trading Signals

*No high-conviction trading signals today — the news cycle is heavy on macro and infrastructure stories without clean per-token catalysts. Signals will resume tomorrow.*

---
*Disclaimer*
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            signals_path, meta_path = self._write_pair(
                tmpdir, skipped_content, {"signals_status": "skipped", "date": "2026-04-28"}
            )
            is_valid, message = validate_signals_file(signals_path, meta_path=meta_path)
            assert is_valid, f"Skip mode with banner should pass. Message: {message}"
            assert "skipped intentionally" in message.lower() or "skipped" in message.lower()
            # Sanity: the banner phrase actually appears (case-insensitive — copy uses
            # capital "No" at sentence start, validator does case-insensitive substring)
            assert SIGNALS_SKIPPED_BANNER_PHRASE.lower() in skipped_content.lower()

    def test_skip_status_without_banner_fails(self):
        """meta.signals_status='skipped' but writeup missing the banner phrase →
        validator must reject (catches mismatch between digest.py and validator)."""
        from scripts.validate_signals_output import validate_signals_file

        broken_content = """# Crypto Trading Signals

## 🎯 Trading Signals

(Some other content that doesn't include the expected phrase.)
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            signals_path, meta_path = self._write_pair(
                tmpdir, broken_content, {"signals_status": "skipped"}
            )
            is_valid, message = validate_signals_file(signals_path, meta_path=meta_path)
            assert not is_valid
            assert "skip banner" in message.lower() or "banner" in message.lower()

    def test_status_ok_runs_strict_path(self):
        """meta.signals_status='ok' → validator must run the existing strict
        checks (emoji lines + portfolio section)."""
        from scripts.validate_signals_output import validate_signals_file

        # Content that would PASS skip-mode but FAIL strict mode (no emoji signals,
        # no portfolio section). With status='ok', strict path runs and rejects.
        banner_only = """# Crypto Trading Signals

## 🎯 Trading Signals

*No high-conviction trading signals today.*
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            signals_path, meta_path = self._write_pair(
                tmpdir, banner_only, {"signals_status": "ok"}
            )
            is_valid, message = validate_signals_file(signals_path, meta_path=meta_path)
            assert not is_valid, "status='ok' must use strict checks (banner alone insufficient)"

    def test_status_reformatted_runs_strict_path(self):
        """meta.signals_status='reformatted' → still runs strict path because
        reformatted output should contain real emoji-prefixed signals."""
        from scripts.validate_signals_output import validate_signals_file

        valid_strict_content = """# Crypto Trading Signals

## 🎯 Trading Signals

🟢 Bitcoin ([$BTC](https://leviathannews.xyz/t/BTC)): BUY - momentum

## 📈 Sentiment Portfolio

### Momentum Strategy
- **Portfolio Value:** `$10,500.00`

### Contrarian Strategy
- **Portfolio Value:** `$9,800.00`

---
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            signals_path, meta_path = self._write_pair(
                tmpdir, valid_strict_content, {"signals_status": "reformatted"}
            )
            is_valid, message = validate_signals_file(signals_path, meta_path=meta_path)
            assert is_valid, f"status='reformatted' with valid strict content should pass. Message: {message}"

    def test_missing_meta_runs_strict_path(self):
        """No --meta flag → validator behaves as before (strict path)."""
        from scripts.validate_signals_output import validate_signals_file

        banner_only = """# Crypto Trading Signals

## 🎯 Trading Signals

*No high-conviction trading signals today.*
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(banner_only)
            f.flush()
            signals_path = Path(f.name)
        try:
            # No meta_path argument — strict path runs
            is_valid, message = validate_signals_file(signals_path)
            assert not is_valid, "Without --meta, banner-only content must fail strict validation"
        finally:
            signals_path.unlink()

    def test_unparseable_meta_runs_strict_path(self):
        """Corrupted meta.json → falls through to strict validation, doesn't
        crash and doesn't open a skip-path bypass."""
        from scripts.validate_signals_output import validate_signals_file

        banner_only = """# Crypto Trading Signals

## 🎯 Trading Signals

*No high-conviction trading signals today.*
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            signals_path = Path(tmpdir) / "signals_x.md"
            meta_path = Path(tmpdir) / "meta_x.json"
            signals_path.write_text(banner_only)
            meta_path.write_text("{not-valid-json")
            # Should not raise; should run strict path and fail (no emoji signals)
            is_valid, message = validate_signals_file(signals_path, meta_path=meta_path)
            assert not is_valid, "Unparseable meta must not bypass strict checks"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
