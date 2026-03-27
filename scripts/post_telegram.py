#!/usr/bin/env python3
"""Post a signals digest to Telegram with links masthead and optional broadcast forward.

Usage:
    # Post yesterday's digest
    python scripts/post_telegram.py

    # Post a specific date
    python scripts/post_telegram.py --date 2026-03-27

    # Dry run (format but don't send)
    python scripts/post_telegram.py --date 2026-03-27 --dry-run

    # Force re-send (bypass forward dedupe)
    python scripts/post_telegram.py --date 2026-03-27 --force
"""

import os
import sys
import argparse
import traceback
from pathlib import Path
from datetime import datetime, timedelta

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.telegram import TelegramClient, format_for_telegram
from squid_digest.telegram.formatter import truncate_html_safely
from squid_digest.config import (
    get_writeup_file_path,
    resolve_digest_url,
    get_github_url,
    load_meta,
    save_meta,
    DEFAULT_BLURB,
    TELEGRAM_CHANNEL_INVITE,
)


def _build_masthead(date, telegram_link=None):
    """Build the links masthead for Part 1.

    Returns (masthead_html, digest_url) so the caller can reuse the URL.
    """
    digest_url = resolve_digest_url(date)
    github_url = get_github_url(date)
    tg_link = telegram_link or TELEGRAM_CHANNEL_INVITE

    meta = load_meta(date)
    blurb = meta.get("blurb") or DEFAULT_BLURB

    masthead = (
        f'<i>{blurb}</i>\n'
        f'Links: ✉️ <a href="{digest_url}">Web</a> • '
        f'⚙️ <a href="{github_url}">GitHub</a> • '
        f'📣 <a href="{tg_link}">Telegram</a>\n\n'
    )
    return masthead, digest_url


def main():
    parser = argparse.ArgumentParser(
        description="Post a signals digest to Telegram",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--date", type=str, help="Date in YYYY-MM-DD format (default: yesterday)")
    parser.add_argument("--file", type=str, help="Path to signals file (overrides --date)")
    parser.add_argument("--dry-run", action="store_true", help="Format and validate but don't send")
    parser.add_argument("--force", action="store_true", help="Bypass forward dedupe check")
    args = parser.parse_args()

    # --- Resolve date and signals file ---
    if args.file:
        signals_path = Path(args.file)
        # Try to parse date from filename
        stem = signals_path.stem
        try:
            date_str = stem.split("_")[-1]
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, IndexError):
            file_date = datetime.now()
    else:
        if args.date:
            date_str = args.date
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            yesterday = datetime.now() - timedelta(days=1)
            date_str = yesterday.strftime("%Y-%m-%d")
            file_date = yesterday
        signals_path = get_writeup_file_path(f"signals_{date_str}.md", file_date)

    if not signals_path.exists():
        print(f"ERROR: Signals file not found: {signals_path}")
        sys.exit(1)

    print(f"Using signals file: {signals_path}")
    print(f"Date: {file_date.strftime('%Y-%m-%d')}")

    if args.dry_run:
        print("DRY RUN MODE — messages will not be sent\n")

    # --- Read and format content ---
    content = signals_path.read_text()
    if not content.strip():
        print("ERROR: Signals file is empty")
        sys.exit(1)

    messages = format_for_telegram(content)
    if not messages:
        print("ERROR: No messages generated from content")
        sys.exit(1)

    total_parts = len(messages)
    print(f"Formatted into {total_parts} message(s)")

    # --- Build Part 1 with masthead ---
    masthead, digest_url = _build_masthead(file_date)
    part1_content = masthead + messages[0]

    # Truncate if needed
    if len(part1_content) > 4096:
        max_content = 4096 - len(masthead) - 50
        messages[0] = truncate_html_safely(messages[0], max_content)
        part1_content = masthead + messages[0]

    # --- Dry run preview ---
    if args.dry_run:
        print("\n" + "=" * 60)
        print("PART 1 PREVIEW (with masthead)")
        print("=" * 60)
        print(f"Length: {len(part1_content)} / 4096")
        print("-" * 60)
        print(part1_content[:500] + ("..." if len(part1_content) > 500 else ""))
        print("-" * 60)
        for i in range(1, total_parts):
            header = f"<b>Part {i + 1}/{total_parts}</b>\n\n"
            part = header + messages[i]
            print(f"\nPART {i + 1}: {len(part)} / 4096 chars")
        print("\n✓ Dry run complete. Remove --dry-run to send.")
        return

    # --- Validate credentials ---
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)
    if not os.getenv("TELEGRAM_CHANNEL_ID"):
        print("ERROR: TELEGRAM_CHANNEL_ID not set")
        sys.exit(1)

    client = TelegramClient()
    channel_id = client.channel_id

    # --- Send Part 1 ---
    print("Sending Part 1 (with masthead)...")
    result1 = client.send_message(part1_content)
    if not result1.get("ok"):
        print(f"✗ Part 1 failed: {result1}")
        sys.exit(1)

    part1_msg_id = result1["result"]["message_id"]
    print(f"✓ Part 1 sent (message_id: {part1_msg_id})")
    save_meta(file_date, {"telegram_part1_message_id": part1_msg_id})

    # --- Edit Part 1 to replace invite link with deep link ---
    deep_link = TelegramClient.get_message_link(channel_id, part1_msg_id)
    if deep_link:
        print(f"Editing Part 1 with deep link: {deep_link}")
        masthead_with_deep, _ = _build_masthead(file_date, telegram_link=deep_link)
        edited_content = masthead_with_deep + messages[0]
        # Re-truncate with updated masthead
        if len(edited_content) > 4096:
            max_content = 4096 - len(masthead_with_deep) - 50
            edited_msg0 = truncate_html_safely(messages[0], max_content)
            edited_content = masthead_with_deep + edited_msg0
        try:
            client.edit_message(part1_msg_id, edited_content)
            print("✓ Part 1 edited with deep link")
        except Exception as e:
            print(f"⚠ Could not edit Part 1 (non-fatal): {e}")

    # --- Send remaining parts (2, 3, …) with correct numbering ---
    failed_parts = []
    for i in range(1, total_parts):
        part_num = i + 1
        header = f"<b>Part {part_num}/{total_parts}</b>\n\n"
        part_content = header + messages[i]

        if len(part_content) > 4096:
            max_msg = 4096 - len(header) - 50
            messages[i] = truncate_html_safely(messages[i], max_msg)
            part_content = header + messages[i]

        try:
            result = client.send_message(part_content)
            if result.get("ok"):
                print(f"✓ Part {part_num}/{total_parts} sent")
            else:
                print(f"✗ Part {part_num} failed: {result}")
                failed_parts.append(part_num)
        except Exception as e:
            print(f"✗ Part {part_num} failed: {e}")
            traceback.print_exc()
            failed_parts.append(part_num)

    if failed_parts:
        print(f"\n✗ {len(failed_parts)} part(s) failed: {failed_parts}")
        sys.exit(1)

    print(f"\n✓ Done — {total_parts} part(s) sent to Telegram")


if __name__ == "__main__":
    main()
