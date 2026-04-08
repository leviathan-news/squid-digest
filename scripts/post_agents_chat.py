#!/usr/bin/env python3
"""Post a photo+caption digest summary to the Leviathan Agent Chat forum.

Sends the Squid Digest splash image with a compact caption to the configured
forum topic in t.me/leviathan_agents, then registers the message with the
Leviathan relay API for chat history visibility.

Usage:
    uv run python scripts/post_agents_chat.py --date 2026-04-08 --dry-run
    uv run python scripts/post_agents_chat.py --date 2026-04-08
    uv run python scripts/post_agents_chat.py --date 2026-04-08 --force
"""

import argparse
import html as html_mod
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.config import (
    get_writeup_file_path,
    resolve_public_digest_url,
    get_github_url,
    load_meta,
    save_meta,
    DEFAULT_BLURB,
    SQUID_DIGEST_IMAGE_URL,
    TELEGRAM_CHANNEL_INVITE,
)


# Max caption length for Telegram sendPhoto
CAPTION_LIMIT = 1024

# Default forum topic ID (General)
DEFAULT_TOPIC_ID = 154


def _format_compact_price(price: float) -> str:
    """Format a price compactly for captions."""
    if price >= 10000:
        return f"${price / 1000:.0f}K"
    elif price >= 1000:
        return f"${price / 1000:.1f}K"
    elif price >= 100:
        return f"${price:.0f}"
    elif price >= 10:
        return f"${price:.1f}"
    elif price >= 1:
        return f"${price:.2f}"
    else:
        return f"${price:.2f}"


def _extract_market_stats(content: str) -> list:
    """Extract (symbol, price, pct_str, pct_float) tuples from Market Snapshot."""
    stats = []
    for m in re.finditer(
        r"•\s*[🔴🟢🟠🟡]\s*\*\*\[(\w+)\]\([^)]*\)\*\*:\s*\$([\d,.]+)\s*\(([+-][\d.]+)%\)",
        content,
    ):
        symbol = m.group(1)
        price = float(m.group(2).replace(",", ""))
        pct_str = m.group(3) + "%"
        pct_float = float(m.group(3))
        stats.append((symbol, price, pct_str, pct_float))
        if len(stats) >= 3:
            break
    return stats


def _format_stats_line(stats: list) -> str:
    """Format stats into a compact line with emoji and cashtags."""
    parts = []
    for symbol, price, pct_str, pct_float in stats:
        emoji = "🟢" if pct_float >= 0 else "🔴"
        compact_price = _format_compact_price(price)
        parts.append(f"{emoji} ${symbol}: {compact_price} ({pct_str})")
    return " · ".join(parts)


def _build_caption(date: datetime, meta: dict, content: str, digest_url: str) -> str:
    """Build a photo caption (max 1024 chars) for the agents chat."""
    github_url = get_github_url(date)
    blurb = html_mod.escape(meta.get("blurb") or DEFAULT_BLURB)
    headline = html_mod.escape(meta.get("top_story_headline", ""))
    comment = html_mod.escape(meta.get("top_story_comment", ""))
    author = html_mod.escape(meta.get("top_story_author", ""))

    stats = _extract_market_stats(content)
    stats_line = _format_stats_line(stats) if stats else ""

    lines = [
        '<b>🦑 SQUID DIGEST 📰</b>',
        f'<i>{date.strftime("%B %d, %Y")}</i>',
        '',
        blurb,
    ]

    if stats_line:
        lines.append('')
        lines.append(stats_line)

    if headline:
        lines.append('')
        lines.append(f'🔥 {headline}')
        if comment and author:
            max_comment = 120
            short_comment = comment[:max_comment - 3] + "..." if len(comment) > max_comment else comment
            lines.append(f'💬 "{short_comment}" — @{author}')

    lines.append('')
    lines.append(
        f'✉️ <a href="{digest_url}">Web</a> · '
        f'⚙️ <a href="{github_url}">GitHub</a> · '
        f'📣 <a href="{TELEGRAM_CHANNEL_INVITE}">Telegram</a>'
    )

    caption = '\n'.join(lines)

    # Progressive trimming to fit 1024 chars
    if len(caption) > CAPTION_LIMIT:
        lines = [l for l in lines if not l.startswith('💬')]
        caption = '\n'.join(lines)

    if len(caption) > CAPTION_LIMIT:
        lines = [l for l in lines if not l.startswith('🔥')]
        caption = '\n'.join(lines)

    if len(caption) > CAPTION_LIMIT:
        over = len(caption) - CAPTION_LIMIT + 3
        blurb = blurb[:-over] + "..."
        lines[3] = blurb
        caption = '\n'.join(lines)

    return caption


def main():
    parser = argparse.ArgumentParser(description="Post photo+caption to Leviathan Agent Chat")
    parser.add_argument("--date", required=True, help="Digest date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--force", action="store_true", help="Bypass dedupe check")
    args = parser.parse_args()

    date = datetime.strptime(args.date, "%Y-%m-%d")
    date_str = date.strftime("%Y-%m-%d")

    # --- Dedupe ---
    meta = load_meta(date)
    if meta.get("agents_chat_message_id") and not args.force:
        print(f"⏭ Already posted to Agent Chat for {date_str}, skipping (use --force to override)")
        return

    # --- Load signals file ---
    signals_path = get_writeup_file_path(f"signals_{date_str}.md", date)
    if not signals_path.exists():
        print(f"ERROR: Signals file not found: {signals_path}")
        sys.exit(1)

    content = signals_path.read_text()
    digest_url = resolve_public_digest_url(date)

    # --- Build caption ---
    caption = _build_caption(date, meta, content, digest_url)
    print(f"Caption ({len(caption)} / {CAPTION_LIMIT} chars):")
    print(caption)
    print(f"\nImage: {SQUID_DIGEST_IMAGE_URL}")

    if args.dry_run:
        print("\n✓ Dry run complete. Remove --dry-run to post.")
        return

    # --- Validate credentials ---
    agents_chat_id = os.getenv("LEVIATHAN_AGENTS_CHAT_ID")
    if not agents_chat_id:
        print("ERROR: LEVIATHAN_AGENTS_CHAT_ID not set")
        sys.exit(1)
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)

    topic_id = int(os.getenv("LEVIATHAN_AGENTS_TOPIC_ID", str(DEFAULT_TOPIC_ID)))

    from squid_digest.telegram import TelegramClient
    client = TelegramClient(require_channel=False)

    # --- Step 1: Post photo via Telegram Bot API ---
    print(f"\nSending photo to Agent Chat (topic_id={topic_id})...")
    try:
        result = client.send_photo(
            photo_url=SQUID_DIGEST_IMAGE_URL,
            caption=caption,
            chat_id=agents_chat_id,
            message_thread_id=topic_id,
        )
        if not result.get("ok"):
            print(f"✗ Agent Chat post failed: {result}")
            sys.exit(1)

        msg_id = result["result"]["message_id"]
        save_meta(date, {"agents_chat_message_id": msg_id})
        print(f"✓ Photo posted to Agent Chat (message_id: {msg_id})")

    except Exception as e:
        print(f"✗ Agent Chat post failed: {e}")
        sys.exit(1)

    # --- Step 2: Register with Leviathan relay (soft failure) ---
    private_key = os.getenv("LEVIATHAN_AGENT_PRIVATE_KEY")
    if private_key:
        try:
            from squid_digest.agents_chat import AgentsChatClient
            relay = AgentsChatClient()
            relay_result = relay.register_post(
                text=caption,
                topic_id=topic_id,
                telegram_message_id=msg_id,
            )
            print(f"✓ Relay registration: {relay_result}")
        except Exception as e:
            print(f"⚠ Relay registration failed (non-fatal): {e}")
    else:
        print("ℹ LEVIATHAN_AGENT_PRIVATE_KEY not set, skipping relay registration")


if __name__ == "__main__":
    main()
