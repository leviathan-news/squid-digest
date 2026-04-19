#!/usr/bin/env python3
"""Post a daily digest summary tweet to X (formerly Twitter).

Posts a single tweet with a branded header, AI-generated blurb, compact
market stats, and a link to the published digest. Includes API-based
dedupe so reruns do not double-post.

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
    resolve_public_digest_url,
    get_canonical_url,
    load_meta,
    save_meta,
    DEFAULT_BLURB,
)

# X wraps all URLs to this length via t.co
X_TCO_URL_LENGTH = 23
# Leave slack for emoji rendering variance
EFFECTIVE_CHAR_LIMIT = 260


def _format_compact_price(price: float) -> str:
    """Format a price compactly for tweets.

    >>> _format_compact_price(71400)
    '$71K'
    >>> _format_compact_price(2179)
    '$2.2K'
    >>> _format_compact_price(0.458)
    '$0.46'
    >>> _format_compact_price(105.18)
    '$105'
    """
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
    """Extract market stats as structured tuples from the Market Snapshot.

    Actual format: • 🟢 **[BTC](url)**: $71,400.00 (+2.15%)

    Returns list of (symbol, price_float, pct_str, pct_float) tuples.
    """
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
    """Format stats tuples into a compact line with emoji and cashtags."""
    parts = []
    for symbol, price, pct_str, pct_float in stats:
        emoji = "\U0001f7e2" if pct_float >= 0 else "\U0001f534"
        compact_price = _format_compact_price(price)
        parts.append(f"{emoji} ${symbol}: {compact_price} ({pct_str})")
    return " \u00b7 ".join(parts)


def _build_tweet(date: datetime, content: str, digest_url: str, blurb: str) -> str:
    """Build a tweet within the 260-char budget.

    Progressively drops stats (OPEN first, then ETH, then all) and
    truncates blurb to fit.
    """
    title = f"\U0001f991 SQUID DIGEST \U0001f4f0 {date.strftime('%B %d, %Y')}"
    cta = f"Read the full digest at {digest_url}"
    stats = _extract_market_stats(content)

    def _real_len(text):
        """Calculate real tweet length (URL counts as 23 regardless of actual length)."""
        return len(text) - len(digest_url) + X_TCO_URL_LENGTH

    def _assemble(blurb_text, stat_items):
        parts = [title]
        if blurb_text:
            parts.append(blurb_text)
        if stat_items:
            parts.append(_format_stats_line(stat_items))
        parts.append(cta)
        return "\n\n".join(parts)

    # Try with full content, progressively trim
    for stat_count in [len(stats), 2, 1, 0]:
        tweet = _assemble(blurb, stats[:stat_count] if stat_count else [])
        if _real_len(tweet) <= EFFECTIVE_CHAR_LIMIT:
            return tweet

    # Still over — truncate blurb
    tweet = _assemble("", [])
    remaining = EFFECTIVE_CHAR_LIMIT - _real_len(tweet) - 4  # 4 for \n\n separator
    if remaining > 20 and blurb:
        truncated_blurb = blurb[:remaining - 3] + "..."
        tweet = _assemble(truncated_blurb, [])
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
        print(f"\u23ed Already tweeted for {date_str} (tweet_id: {meta['tweet_id']}), skipping")
        return

    # --- Load signals file ---
    signals_path = get_writeup_file_path(f"signals_{date_str}.md", date)
    if not signals_path.exists():
        print(f"ERROR: Signals file not found: {signals_path}")
        sys.exit(1)

    content = signals_path.read_text()

    # Use canonical URL for X (safe, always points to published post)
    digest_url = resolve_public_digest_url(date)
    blurb = meta.get("blurb") or DEFAULT_BLURB

    # --- Build tweet ---
    tweet = _build_tweet(date, content, digest_url, blurb)
    real_len = len(tweet) - len(digest_url) + X_TCO_URL_LENGTH
    print(f"Tweet ({real_len} chars / {EFFECTIVE_CHAR_LIMIT}):")
    print(tweet)

    if args.dry_run:
        print("\n\u2713 Dry run complete. Remove --dry-run to post.")
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
                print(f"\u23ed Digest tweet already exists (id: {tweet_id}), skipping")
                save_meta(date, {"tweet_id": tweet_id, "tweet_status": "ok"})
                return
        else:
            print("\u2139 X_ACCOUNT_USERNAME not set, skipping API dedupe check")

    # --- Post ---
    print("\nPosting to X...")
    try:
        result = client.post_tweet(tweet)
        tweet_id = result.get("data", {}).get("id")
        if tweet_id:
            save_meta(date, {"tweet_id": tweet_id, "tweet_status": "ok"})
            print(f"\u2713 Posted: https://x.com/i/web/status/{tweet_id}")
        else:
            print(f"\u26a0 Post returned unexpected response: {result}")
            save_meta(date, {"tweet_status": "FAILED"})
            sys.exit(1)
    except Exception as e:
        print(f"\u2717 Failed to post: {e}")
        save_meta(date, {"tweet_status": "FAILED"})
        sys.exit(1)


if __name__ == "__main__":
    main()
