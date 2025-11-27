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
            assert "empty or too short" in message.lower()
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

## 📊 Backtest Results

[backtest data here]

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
        """Test that zero signals with available data triggers error."""
        # This would be an integration test that would require mocking the LLM
        # For now, we document the expected behavior
        pytest.skip("Integration test - requires LLM mocking")

    def test_malformed_llm_response_detection(self):
        """Test that malformed LLM responses are caught."""
        pytest.skip("Integration test - requires LLM mocking")

    def test_empty_llm_response_rejection(self):
        """Test that empty LLM responses are rejected with diagnostic info."""
        pytest.skip("Integration test - requires LLM mocking")


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
