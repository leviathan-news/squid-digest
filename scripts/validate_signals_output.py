#!/usr/bin/env python3
"""
Validation script to ensure trading signals file has actual content.

This script validates that a generated signals markdown file contains:
1. At least one actual trading signal (not just empty sections)
2. Proper formatting

Usage:
    python scripts/validate_signals_output.py writeup/2025/11/27/signals_2025-11-27.md

Exit codes:
    0: Validation passed
    1: Validation failed (no signals found, file missing, etc.)
"""

import sys
import re
from pathlib import Path


def validate_signals_file(filepath: Path) -> tuple[bool, str]:
    """
    Validate that a signals markdown file has actual trading signals.

    Args:
        filepath: Path to the signals markdown file

    Returns:
        Tuple of (is_valid, message)
    """
    # Check file exists
    if not filepath.exists():
        return False, f"Signal file does not exist: {filepath}"

    if not filepath.is_file():
        return False, f"Path is not a file: {filepath}"

    # Read file content
    try:
        with open(filepath, "r") as f:
            content = f.read()
    except Exception as e:
        return False, f"Could not read signal file: {e}"

    # Check for empty file
    if not content or len(content.strip()) == 0:
        return False, "Signal file is empty"

    # Look for trading signals section
    # The file should have a "## 🎯 Trading Signals" section
    trading_signals_header = "## 🎯 Trading Signals"
    if trading_signals_header not in content:
        return False, f"Trading signals section not found (missing '{trading_signals_header}')"

    # Extract the trading signals section
    # Everything between the header and the next section (or file end)
    parts = content.split(trading_signals_header, 1)
    if len(parts) < 2:
        return False, "Could not extract trading signals section"

    signals_section = parts[1]

    # Find the end of signals section (next ## header or end of file)
    next_section_match = re.search(r'\n##\s+', signals_section)
    if next_section_match:
        signals_section = signals_section[:next_section_match.start()]

    signals_section = signals_section.strip()

    # Check for empty signals section (just whitespace)
    if not signals_section or len(signals_section) < 10:
        return False, (
            f"Trading signals section is empty or too short ({len(signals_section)} chars). "
            f"This indicates signal generation failed."
        )

    # Look for signal patterns (emoji markers)
    # Valid signals start with: 🟢, 🔴, 🟡, 🟠, ⚪
    signal_emojis = ['🟢', '🔴', '🟡', '🟠', '⚪']
    has_signals = any(emoji in signals_section for emoji in signal_emojis)

    if not has_signals:
        return False, (
            f"No trading signals found in signals section. "
            f"Signals should contain emoji markers ({', '.join(signal_emojis)}). "
            f"Section content: {signals_section[:200]}..."
        )

    # Count actual signal lines (lines starting with emoji)
    signal_lines = [
        line.strip() for line in signals_section.split('\n')
        if line.strip() and any(line.strip().startswith(emoji) for emoji in signal_emojis)
    ]

    if not signal_lines:
        return False, (
            f"No valid signal lines found. Expected lines starting with emoji markers. "
            f"Section content: {signals_section[:200]}..."
        )

    # Validate signal format
    # Each signal should match pattern: EMOJI Token (Symbol): SIGNAL_TYPE - reason
    signal_pattern = re.compile(
        r'^[🟢🔴🟡🟠⚪]\s+[^(]+\s*\([^\)]*\):\s*(STRONG )?(BUY|SELL|WEAK)',
        re.MULTILINE
    )

    valid_signals = [
        line for line in signal_lines
        if signal_pattern.search(line)
    ]

    if not valid_signals:
        # Signals exist but may have wrong format - show what we got
        return False, (
            f"Signal format validation failed. Found {len(signal_lines)} signal lines "
            f"but none match expected format. "
            f"Sample line: {signal_lines[0] if signal_lines else '(none)'}"
        )

    # CRITICAL: Check for backtest section
    # If trading signals exist, we MUST have backtest results
    # This prevents the 2025-11-29 failure mode where signals were generated but not backtested
    backtest_header = "## 📈 Backtest Results"
    if backtest_header not in content:
        return False, (
            f"CRITICAL: Trading signals found ({len(valid_signals)} signals) but backtest section is missing! "
            f"This indicates signal parsing failed (likely LLM format mismatch). "
            f"Expected to find '{backtest_header}' section after trading signals."
        )

    # Extract backtest section and validate it has content
    backtest_parts = content.split(backtest_header, 1)
    if len(backtest_parts) < 2:
        return False, "Could not extract backtest section"

    backtest_section = backtest_parts[1]
    # Find the end of backtest section (--- separator or end of file)
    separator_match = re.search(r'\n---\n', backtest_section)
    if separator_match:
        backtest_section = backtest_section[:separator_match.start()]

    backtest_section = backtest_section.strip()

    # Check for meaningful backtest content
    # Should contain portfolio values, strategy names, etc.
    if len(backtest_section) < 100:
        return False, (
            f"Backtest section exists but is too short ({len(backtest_section)} chars). "
            f"This indicates backtest may have failed."
        )

    # Check for key backtest indicators
    required_backtest_terms = ["Buy the News", "Sell the News", "Portfolio Value"]
    missing_terms = [term for term in required_backtest_terms if term not in backtest_section]

    if missing_terms:
        return False, (
            f"Backtest section missing required content: {', '.join(missing_terms)}. "
            f"This indicates incomplete backtest results."
        )

    # All validations passed
    message = f"✓ Signals file validation passed ({len(valid_signals)} valid signals found, backtest section present)"
    return True, message


def main():
    """Run validation on provided signal file path."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_signals_output.py <path_to_signals_file>")
        print("\nExample: python scripts/validate_signals_output.py writeup/2025/11/27/signals_2025-11-27.md")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    is_valid, message = validate_signals_file(filepath)

    print(message)

    if is_valid:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
