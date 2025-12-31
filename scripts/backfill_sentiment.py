#!/usr/bin/env python3
"""
Backfill sentiment state from historical signal files.

This script processes historical signal files to build up sentiment state
before the new sentiment-based portfolio system goes live.

Usage:
    python scripts/backfill_sentiment.py --weeks 4

This will:
1. Find all signal files from the past N weeks
2. Process them chronologically, applying decay between days
3. Save the final sentiment state to writeup/sentiment_state.json
"""

import argparse
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
import re

# Add project paths
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from squid_digest.backtest.signal_parser import SignalParser
from squid_digest.backtest.sentiment_state import SentimentTracker

# Default paths
WRITEUP_DIR = PROJECT_ROOT / "writeup"
SENTIMENT_STATE_FILE = WRITEUP_DIR / "sentiment_state.json"


def find_signal_files(writeup_dir: Path, start_date: date) -> list[Path]:
    """
    Find all signal files from start_date to today.

    Signal files are named: signals_YYYY-MM-DD.md
    They may be in subdirectories like writeup/2025/12/20/signals_2025-12-20.md
    """
    signal_files = []

    for filepath in writeup_dir.rglob("signals_*.md"):
        # Extract date from filename
        match = re.search(r'signals_(\d{4}-\d{2}-\d{2})(?:_[a-z_]+)?\.md', filepath.name)
        if not match:
            continue

        file_date = datetime.strptime(match.group(1), '%Y-%m-%d').date()

        if file_date >= start_date:
            signal_files.append((file_date, filepath))

    # Sort by date
    signal_files.sort(key=lambda x: x[0])

    return signal_files


def backfill_sentiment(
    weeks: int = 4,
    writeup_dir: Path = WRITEUP_DIR,
    state_file: Path = SENTIMENT_STATE_FILE,
    verbose: bool = True,
) -> dict:
    """
    Process historical signal files to build sentiment state.

    Args:
        weeks: Number of weeks of history to process
        writeup_dir: Directory containing signal files
        state_file: Path to save sentiment state
        verbose: Print progress information

    Returns:
        Summary dict with processing statistics
    """
    # Calculate start date
    start_date = date.today() - timedelta(weeks=weeks)

    if verbose:
        print(f"Backfilling sentiment from {start_date} to today")
        print(f"Looking for signal files in: {writeup_dir}")

    # Find all signal files in range
    signal_files = find_signal_files(writeup_dir, start_date)

    if not signal_files:
        print(f"No signal files found from {start_date} onwards")
        return {"files_processed": 0, "signals_applied": 0, "tokens_tracked": 0}

    if verbose:
        print(f"Found {len(signal_files)} signal files to process")

    # Initialize fresh sentiment tracker
    tracker = SentimentTracker(state_file)
    tracker.reset()  # Start fresh

    # Initialize signal parser
    signal_parser = SignalParser(writeup_dir)

    total_signals = 0
    last_date = None

    for file_date, filepath in signal_files:
        # Apply decay from last processed date to this date
        if last_date is not None and file_date > last_date:
            days_gap = (file_date - last_date).days
            if days_gap > 0:
                decay_info = tracker.apply_decay(file_date)
                if verbose and decay_info:
                    decayed_tokens = len(decay_info)
                    if decayed_tokens > 0:
                        print(f"  Applied decay for {days_gap} days to {decayed_tokens} tokens")

        # Parse signals from file
        try:
            signals = signal_parser.parse_file(filepath)
        except Exception as e:
            print(f"Warning: Could not parse {filepath.name}: {e}")
            continue

        if not signals:
            if verbose:
                print(f"  {filepath.name}: No signals parsed")
            last_date = file_date
            continue

        # Apply each signal
        signals_today = 0
        for signal in signals:
            spike = tracker.apply_signal(
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                signal_date=file_date,
                token_name=signal.token_name,
            )
            if spike != 0:
                signals_today += 1
                total_signals += 1

        if verbose:
            print(f"  {filepath.name}: Applied {signals_today} signals")

        last_date = file_date

    # Update last processed date
    if last_date:
        tracker.last_processed_date = last_date.isoformat()

    # Save final state
    tracker.save()

    # Generate summary
    all_sentiments = tracker.get_all_sentiments()
    positive_count = sum(1 for s in all_sentiments.values() if s > 0)
    negative_count = sum(1 for s in all_sentiments.values() if s < 0)

    summary = {
        "files_processed": len(signal_files),
        "signals_applied": total_signals,
        "tokens_tracked": len(all_sentiments),
        "positive_sentiment": positive_count,
        "negative_sentiment": negative_count,
        "start_date": start_date.isoformat(),
        "end_date": last_date.isoformat() if last_date else None,
    }

    if verbose:
        print(f"\n=== Backfill Complete ===")
        print(f"Files processed: {summary['files_processed']}")
        print(f"Signals applied: {summary['signals_applied']}")
        print(f"Tokens tracked: {summary['tokens_tracked']}")
        print(f"  Positive sentiment: {summary['positive_sentiment']}")
        print(f"  Negative sentiment: {summary['negative_sentiment']}")
        print(f"\nSaved to: {state_file}")

        # Show top sentiment tokens
        ranked = tracker.get_ranked_tokens()
        if ranked:
            print(f"\nTop 5 positive sentiment:")
            for symbol, score in ranked[:5]:
                if score > 0:
                    print(f"  {symbol}: +{score:.2f}")

            print(f"\nTop 5 negative sentiment:")
            for symbol, score in ranked[-5:]:
                if score < 0:
                    print(f"  {symbol}: {score:.2f}")

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Backfill sentiment state from historical signals"
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=4,
        help="Number of weeks of history to process (default: 4)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=SENTIMENT_STATE_FILE,
        help=f"Output file for sentiment state (default: {SENTIMENT_STATE_FILE})"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    backfill_sentiment(
        weeks=args.weeks,
        state_file=args.output,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
