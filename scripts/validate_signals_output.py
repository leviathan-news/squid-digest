#!/usr/bin/env python3
"""
Validation script to ensure trading signals file has actual content.

This script validates that a generated signals markdown file contains:
1. At least one actual trading signal (not just empty sections)
2. Proper formatting

When --meta is provided and meta["signals_status"] == "skipped", a relaxed
validation path runs that confirms the subscriber-facing skip banner is
present and bypasses the emoji-line and portfolio-section requirements.

Usage:
    python scripts/validate_signals_output.py writeup/2025/11/27/signals_2025-11-27.md
    python scripts/validate_signals_output.py writeup/2025/11/27/signals_2025-11-27.md \\
        --meta writeup/2025/11/27/meta_2025-11-27.json

Exit codes:
    0: Validation passed
    1: Validation failed (no signals found, file missing, etc.)
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Stable substring of the subscriber banner shipped from scripts/digest.py
# (SIGNALS_SKIPPED_BANNER_PHRASE). Cosmetic copy changes around this phrase
# stay safe as long as the phrase itself is preserved.
SIGNALS_SKIPPED_BANNER_PHRASE = "no high-conviction trading signals today"


def _read_signals_status(meta_path: Path) -> tuple[str | None, str | None]:
    """Read signals_status from meta.json. Returns (status, error_message).

    Status is None if the meta file is missing/unreadable/missing-key. Caller
    decides whether that's fatal (it is not — strict path runs in that case).
    """
    if not meta_path.exists():
        return None, f"Meta file does not exist: {meta_path}"
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
    except Exception as e:
        return None, f"Could not parse meta file: {e}"
    return meta.get("signals_status"), None


def validate_signals_file(filepath: Path, meta_path: Path | None = None) -> tuple[bool, str]:
    """
    Validate that a signals markdown file has actual trading signals.

    Args:
        filepath: Path to the signals markdown file
        meta_path: Optional path to sibling meta.json. When provided and
            meta["signals_status"] == "skipped", runs the relaxed skip-mode
            check (banner present, header present, portfolio not required).

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

    # Skip-mode: when meta records signals_status="skipped", run relaxed validation.
    # Anything else (status="ok", "reformatted", missing meta, unparseable meta) flows
    # through the strict path below — reformatted signals must still be real.
    if meta_path is not None:
        signals_status, _meta_err = _read_signals_status(meta_path)
        if signals_status == "skipped":
            # Banner must be present in the trading signals section so we know the
            # skip was intentional and not just an empty section.
            if SIGNALS_SKIPPED_BANNER_PHRASE.lower() not in content.lower():
                return False, (
                    f"meta.signals_status='skipped' but signals file is missing the "
                    f"expected skip banner phrase ('{SIGNALS_SKIPPED_BANNER_PHRASE}'). "
                    f"This indicates a mismatch between digest.py and the validator."
                )
            return True, (
                "✓ Validation passed (signals skipped intentionally; "
                "status=skipped, banner present)"
            )

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
    # Each signal should match pattern: EMOJI Token (Symbol or markdown link): SIGNAL_TYPE - reason
    # Handle both simple (Symbol) and markdown ([$SYM](url)) formats
    signal_pattern = re.compile(
        r'^[🟢🔴🟡🟠⚪]\s+.+?:\s*(STRONG\s+)?(BUY|SELL|WEAK)',
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

    # CRITICAL: Check for portfolio/backtest section
    # If trading signals exist, we MUST have portfolio results
    # This prevents the 2025-11-29 failure mode where signals were generated but not backtested
    # Support both old format (Backtest Results) and new format (Sentiment Portfolio)
    portfolio_header = "## 📈 Sentiment Portfolio"
    backtest_header = "## 📈 Backtest Results"
    has_portfolio_section = portfolio_header in content or backtest_header in content
    if not has_portfolio_section:
        return False, (
            f"CRITICAL: Trading signals found ({len(valid_signals)} signals) but portfolio section is missing! "
            f"This indicates signal parsing failed (likely LLM format mismatch). "
            f"Expected to find '{portfolio_header}' or '{backtest_header}' section after trading signals."
        )

    # Extract portfolio/backtest section and validate it has content
    # Use whichever header is present
    active_header = portfolio_header if portfolio_header in content else backtest_header
    backtest_parts = content.split(active_header, 1)
    if len(backtest_parts) < 2:
        return False, "Could not extract portfolio/backtest section"

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

    # Check for key portfolio/backtest indicators
    # Support both old format (Buy/Sell the News) and new format (Momentum/Contrarian Strategy)
    old_format_terms = ["Buy the News", "Sell the News", "Portfolio Value"]
    new_format_terms = ["Momentum Strategy", "Contrarian Strategy", "Portfolio Value"]

    has_old_format = all(term in backtest_section for term in old_format_terms)
    has_new_format = all(term in backtest_section for term in new_format_terms)

    if not has_old_format and not has_new_format:
        return False, (
            f"Portfolio section missing required content. "
            f"Expected either {old_format_terms} or {new_format_terms}. "
            f"This indicates incomplete portfolio/backtest results."
        )

    # All validations passed
    message = f"✓ Signals file validation passed ({len(valid_signals)} valid signals found, portfolio section present)"
    return True, message


def main():
    """Run validation on provided signal file path."""
    parser = argparse.ArgumentParser(
        description="Validate that a generated signals markdown file has actual content."
    )
    parser.add_argument(
        "signals_file",
        type=Path,
        help="Path to the signals markdown file (e.g. writeup/2026/04/28/signals_2026-04-28.md)",
    )
    parser.add_argument(
        "--meta",
        type=Path,
        default=None,
        help=(
            "Optional path to sibling meta.json. When meta.signals_status == 'skipped', "
            "runs relaxed validation (banner check only, no portfolio section required)."
        ),
    )
    args = parser.parse_args()

    is_valid, message = validate_signals_file(args.signals_file, meta_path=args.meta)

    print(message)

    if is_valid:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
