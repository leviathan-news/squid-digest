#!/usr/bin/env python3
"""Post most recent newsletter to SQUID Cave channel.

This script posts the first page of the daily digest to the SQUID Cave
Telegram channel with a masthead and links to the full content.

Usage:
    # Post most recent newsletter (dry run)
    uv run python scripts/post_telegram_cave.py --dry-run

    # Post most recent newsletter (live)
    uv run python scripts/post_telegram_cave.py

    # Post specific date
    uv run python scripts/post_telegram_cave.py --date 2026-01-24
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.telegram import TelegramClient, format_for_telegram
from squid_digest.config import WRITEUP_DIR


def get_latest_signals_file() -> Path:
    """Find most recent signals file."""
    signals_files = sorted(WRITEUP_DIR.rglob("signals_*.md"), reverse=True)
    if not signals_files:
        raise FileNotFoundError("No signals files found in writeup directory")
    return signals_files[0]


def get_signals_file_for_date(date: datetime) -> Path:
    """Find signals file for a specific date."""
    year = date.year
    month = f"{date.month:02d}"
    day = f"{date.day:02d}"
    date_str = date.strftime("%Y-%m-%d")

    filepath = WRITEUP_DIR / str(year) / month / day / f"signals_{date_str}.md"
    if not filepath.exists():
        raise FileNotFoundError(f"Signals file not found: {filepath}")
    return filepath


def get_canonical_url(date: datetime) -> str:
    """Generate canonical URL for digest on web."""
    month = date.strftime("%B").lower()  # january, february, etc.
    day = date.day  # No leading zero
    year = date.year
    return f"https://digest.leviathannews.xyz/leviathan-news-daily-digest-{month}-{day}-{year}/"


def get_github_url(date: datetime) -> str:
    """Generate GitHub URL for digest markdown file."""
    return (
        f"https://github.com/leviathan-news/squid-digest/blob/main/writeup/"
        f"{date.year}/{date.month:02d}/{date.day:02d}/signals_{date.strftime('%Y-%m-%d')}.md"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Post digest to SQUID Cave Telegram channel"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview message without sending",
    )
    parser.add_argument(
        "--date",
        help="Date in YYYY-MM-DD format (default: most recent)",
    )
    args = parser.parse_args()

    # Find signals file
    if args.date:
        date = datetime.strptime(args.date, "%Y-%m-%d")
        signals_file = get_signals_file_for_date(date)
    else:
        signals_file = get_latest_signals_file()
        # Extract date from filename: signals_2026-01-24.md -> 2026-01-24
        date_str = signals_file.stem.split("_")[-1]
        date = datetime.strptime(date_str, "%Y-%m-%d")

    print(f"Using signals file: {signals_file}")
    print(f"Date: {date.strftime('%Y-%m-%d')}")

    # Read and format content
    content = signals_file.read_text()
    messages = format_for_telegram(content)

    if not messages:
        print("Error: No content generated from signals file")
        sys.exit(1)

    page1 = messages[0]

    # Generate URLs
    canonical_url = get_canonical_url(date)
    github_url = get_github_url(date)

    # Build full message with masthead and footer
    masthead = "🐙 <b>SQUID Digest</b>\n\n"
    footer = f'\n\n📰 <a href="{canonical_url}">Read on Web</a> • <a href="{github_url}">View on GitHub</a>'
    full_message = masthead + page1 + footer

    if args.dry_run:
        print("\n" + "=" * 60)
        print("SQUID Cave Preview (DRY RUN)")
        print("=" * 60)
        print(f"Canonical URL: {canonical_url}")
        print(f"GitHub URL: {github_url}")
        print(f"Message length: {len(full_message)} chars (limit: 4096)")
        print("-" * 60)
        # Show full message (it's HTML but readable)
        print(full_message)
        print("-" * 60)

        if len(full_message) > 4096:
            print(f"⚠️  WARNING: Message exceeds 4096 char limit by {len(full_message) - 4096} chars")
            print("   Message will be truncated when sent.")
        else:
            print(f"✓ Message is within limit ({4096 - len(full_message)} chars remaining)")

        return

    # Send to SQUID Cave
    print("\nSending to SQUID Cave...")
    try:
        # require_channel=False since we're using send_to_cave with its own channel
        client = TelegramClient(require_channel=False)
        result = client.send_to_cave(page1, canonical_url, github_url)

        if result.get("ok"):
            print(f"✓ Posted to SQUID Cave successfully")
            message_id = result.get("result", {}).get("message_id")
            if message_id:
                print(f"  Message ID: {message_id}")
        else:
            print(f"✗ Failed to post: {result}")
            sys.exit(1)

    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        print("  Make sure TELEGRAM_BOT_TOKEN and TELEGRAM_CAVE_CHANNEL_ID are set")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error posting to SQUID Cave: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
