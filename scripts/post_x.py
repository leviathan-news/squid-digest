#!/usr/bin/env python3
"""Post a daily digest summary tweet to X (formerly Twitter).

Posts a single tweet with key market stats and a link to the full
digest on digest.leviathannews.xyz.  Includes API-based dedupe so
reruns do not double-post.

Usage:
    uv run python scripts/post_x.py --date 2026-03-27 --dry-run
    uv run python scripts/post_x.py --date 2026-03-27
    uv run python scripts/post_x.py --date 2026-03-27 --force
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.config import (
    get_writeup_file_path,
    resolve_digest_url,
    load_meta,
    save_meta,
)

# X wraps all URLs to this length via t.co
X_TCO_URL_LENGTH = 23
EFFECTIVE_CHAR_LIMIT = 280


def _extract_market_stats(content: str) -> str:
    """Pull the top 3 movers from the Market Snapshot section."""
    lines = []
    # Find bullet lines like "• 🔴 BTC: $69,447.00 (-2.73%)"
    for m in re.finditer(r"•\s*[🔴🟢]\s*(\w+):\s*\$[\d,.]+\s*\(([+-][\d.]+%)\)", content):
        symbol, pct = m.group(1), m.group(2)
        lines.append(f"{symbol} {pct}")
        if len(lines) >= 3:
            break
    return " • ".join(lines) if lines else ""


def _extract_top_headline(content: str) -> str:
    """Pull the first headline from the Top Stories section."""
    m = re.search(r"\d+\.\s+(.+?)(?:\n|$)", content)
    if m:
        headline = m.group(1).strip()
        # Strip markdown bold/source suffixes
        headline = re.sub(r"\s*-\s*\[.*?\]\(.*?\)\s*$", "", headline)
        headline = headline.replace("**", "").strip()
        if len(headline) > 80:
            headline = headline[:77] + "..."
        return headline
    return ""


def _build_tweet(date: datetime, content: str, digest_url: str) -> str:
    """Build a tweet within the 280-char budget."""
    title = f"\U0001f4ca Crypto Trading Signals - {date.strftime('%b %d, %Y')}"
    stats = _extract_market_stats(content)
    headline = _extract_top_headline(content)

    # URL always present — t.co wraps to 23 chars
    url_line = f"\U0001f517 {digest_url}"

    # Budget: title + \n\n + stats + \n\n + headline + \n\n + url (23 chars)
    # Start with everything, trim if over budget
    parts = [title]
    if stats:
        parts.append(stats)
    if headline:
        parts.append(headline)
    parts.append(url_line)

    tweet = "\n\n".join(parts)

    # Calculate real length (URL counts as 23 regardless of actual length)
    real_length = len(tweet) - len(digest_url) + X_TCO_URL_LENGTH

    # Drop headline first if over budget
    if real_length > EFFECTIVE_CHAR_LIMIT and headline:
        parts = [p for p in parts if p != headline]
        tweet = "\n\n".join(parts)
        real_length = len(tweet) - len(digest_url) + X_TCO_URL_LENGTH

    # Drop stats if still over
    if real_length > EFFECTIVE_CHAR_LIMIT and stats:
        parts = [p for p in parts if p != stats]
        tweet = "\n\n".join(parts)

    return tweet


def main():
    parser = argparse.ArgumentParser(description="Post digest tweet to X")
    parser.add_argument("--date", required=True, help="Digest date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--force", action="store_true", help="Bypass dedupe checks")
    args = parser.parse_args()

    date = datetime.strptime(args.date, "%Y-%m-%d")
    date_str = date.strftime("%Y-%m-%d")

    # --- Fast-path dedupe ---
    meta = load_meta(date)
    if meta.get("tweet_id") and not args.force:
        print(f"⏭ Already tweeted for {date_str} (tweet_id: {meta['tweet_id']}), skipping")
        return

    # --- Load signals file ---
    signals_path = get_writeup_file_path(f"signals_{date_str}.md", date)
    if not signals_path.exists():
        print(f"ERROR: Signals file not found: {signals_path}")
        sys.exit(1)

    content = signals_path.read_text()
    digest_url = resolve_digest_url(date)

    # --- Build tweet ---
    tweet = _build_tweet(date, content, digest_url)
    real_len = len(tweet) - len(digest_url) + X_TCO_URL_LENGTH
    print(f"Tweet ({real_len} chars / {EFFECTIVE_CHAR_LIMIT}):")
    print(tweet)

    if args.dry_run:
        print("\n✓ Dry run complete. Remove --dry-run to post.")
        return

    # --- Validate X credentials ---
    required_vars = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        sys.exit(1)

    from squid_digest.x import XClient
    client = XClient()

    # --- Authoritative dedupe via X search API (fail-open) ---
    if not args.force:
        username = os.getenv("X_ACCOUNT_USERNAME", "")
        if username:
            start_of_day = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
            query = f'from:{username} url:"{digest_url}"'
            existing = client.search_recent(query, start_time=start_of_day.isoformat())
            if existing:
                tweet_id = existing[0].get("id", "unknown")
                print(f"⏭ Digest tweet already exists (id: {tweet_id}), skipping")
                save_meta(date, {"tweet_id": tweet_id})
                return
        else:
            print("ℹ X_ACCOUNT_USERNAME not set, skipping API dedupe check")

    # --- Post ---
    print("\nPosting to X...")
    try:
        result = client.post_tweet(tweet)
        tweet_id = result.get("data", {}).get("id")
        if tweet_id:
            save_meta(date, {"tweet_id": tweet_id})
            print(f"✓ Posted: https://x.com/i/web/status/{tweet_id}")
        else:
            print(f"⚠ Post returned unexpected response: {result}")
    except Exception as e:
        print(f"✗ Failed to post: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
