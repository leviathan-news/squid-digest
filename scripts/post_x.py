#!/usr/bin/env python3
"""Post a daily digest as native X content with its source link in a reply.

The root contains the full readable digest without an outbound URL. The
published digest link is the root's first reply, so retrying that reply never
needs to duplicate the editorial root.

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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
    load_meta,
    save_meta,
    DEFAULT_BLURB,
)

NATIVE_DIGEST_ROOT_MAX_CHARS = 25_000


def _native_text(markdown: str) -> str:
    """Keep digest prose while removing Markdown syntax and every root URL."""
    text = str(markdown or '')
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'<https?://[^>]+>', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'(?m)^\s{0,3}#{1,6}\s*', '', text)
    text = text.replace('**', '').replace('__', '').replace('`', '')
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    return text.strip()


def _build_native_root(date: datetime, content: str, blurb: str) -> str:
    """Build a URL-free long-form root; never silently truncate editorial text."""
    title = f"\U0001f991 SQUID DIGEST \U0001f4f0 {date.strftime('%B %d, %Y')}"
    parts = [title, _native_text(blurb), _native_text(content)]
    root = '\n\n'.join(part for part in parts if part).strip()
    if not root:
        raise ValueError('native digest root is empty')
    if re.search(r'https?://', root, flags=re.IGNORECASE):
        raise ValueError('native digest root contains an outbound URL')
    if len(root) > NATIVE_DIGEST_ROOT_MAX_CHARS:
        raise ValueError(
            f'native digest root exceeds {NATIVE_DIGEST_ROOT_MAX_CHARS} characters; '
            'refusing to truncate editorial content'
        )
    return root


def _tracked_digest_url(digest_url: str) -> str:
    """Add stable attribution to the canonical URL carried by the first reply."""
    parsed = urlsplit(digest_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({
        'utm_source': 'x',
        'utm_medium': 'social',
        'utm_campaign': 'squid_digest',
    })
    return urlunsplit(parsed._replace(query=urlencode(query)))


def _build_source_reply(digest_url: str) -> str:
    return f"Read the complete digest and archive: {_tracked_digest_url(digest_url)}"


def _root_search_query(date: datetime, username: str) -> str:
    return f'from:{username} "SQUID DIGEST" "{date.strftime("%B %d, %Y")}"'


def main():
    parser = argparse.ArgumentParser(description="Post digest tweet to X")
    parser.add_argument("--date", required=True, help="Digest date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--force", action="store_true", help="Bypass dedupe checks")
    args = parser.parse_args()

    date = datetime.strptime(args.date, "%Y-%m-%d")
    date_str = date.strftime("%Y-%m-%d")

    meta = load_meta(date)

    # --- Load signals file ---
    signals_path = get_writeup_file_path(f"signals_{date_str}.md", date)
    if not signals_path.exists():
        print(f"ERROR: Signals file not found: {signals_path}")
        sys.exit(1)

    content = signals_path.read_text()

    # Use canonical URL for X (safe, always points to published post)
    digest_url = resolve_public_digest_url(date)
    blurb = meta.get("blurb") or DEFAULT_BLURB

    # --- Build the URL-free root and its canonical-link reply ---
    try:
        root = _build_native_root(date, content, blurb)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        save_meta(date, {"tweet_status": "FAILED"})
        sys.exit(1)
    tracked_digest_url = _tracked_digest_url(digest_url)
    source_reply = _build_source_reply(digest_url)
    print(f"Native root ({len(root)} chars / {NATIVE_DIGEST_ROOT_MAX_CHARS}):")
    print(root)
    print("\nFirst reply:")
    print(source_reply)

    if args.dry_run:
        print("\n\u2713 Dry run complete. Remove --dry-run to post.")
        return

    # --- Validate X credentials ---
    required_vars = [
        "X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET",
        "X_ACCOUNT_USERNAME",
    ]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        sys.exit(1)

    from squid_digest.x import XClient
    client = XClient()

    root_id = meta.get('tweet_id')
    reply_id = meta.get('tweet_reply_id')
    username = os.getenv("X_ACCOUNT_USERNAME", "")
    start_of_day = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)

    # A root has no URL, so its date-stamped masthead—not the reply URL—is the
    # crash-recovery key. Search remains fail-open, matching the prior runner.
    if not args.force and not root_id and username:
        existing = client.search_recent(
            _root_search_query(date, username), start_time=start_of_day.isoformat(),
        )
        if existing and existing[0].get('id'):
            root_id = existing[0]['id']
            save_meta(date, {"tweet_id": root_id, "tweet_status": "ROOT_POSTED"})
            print(f"\u23ed Native digest root already exists (id: {root_id})")
    print("\nPosting to X...")
    if not root_id:
        try:
            result = client.post_tweet(root)
            root_id = result.get("data", {}).get("id")
            if not root_id:
                raise RuntimeError(f"root post returned unexpected response: {result}")
            save_meta(date, {"tweet_id": root_id, "tweet_status": "ROOT_POSTED"})
            print(f"\u2713 Native root posted: https://x.com/i/web/status/{root_id}")
        except Exception as exc:
            print(f"\u2717 Failed to post native root: {exc}")
            save_meta(date, {"tweet_status": "FAILED"})
            sys.exit(1)

    if not args.force and not reply_id and username:
        existing = client.search_recent(
            f'from:{username} url:"{tracked_digest_url}"',
            start_time=start_of_day.isoformat(),
        )
        reply = next((row for row in existing if str(row.get('id')) != str(root_id)), None)
        if reply and reply.get('id'):
            reply_id = reply['id']
            save_meta(date, {"tweet_reply_id": reply_id, "tweet_status": "ok"})
            print(f"\u23ed Digest source reply already exists (id: {reply_id})")

    if reply_id and not args.force:
        print(f"\u23ed Digest distribution already complete (root={root_id}, reply={reply_id})")
        return

    try:
        result = client.post_tweet(source_reply, in_reply_to_tweet_id=str(root_id))
        reply_id = result.get("data", {}).get("id")
        if not reply_id:
            raise RuntimeError(f"source reply returned unexpected response: {result}")
        save_meta(date, {
            "tweet_id": root_id,
            "tweet_reply_id": reply_id,
            "tweet_status": "ok",
        })
        print(f"\u2713 Source reply posted: https://x.com/i/web/status/{reply_id}")
    except Exception as exc:
        print(f"\u2717 Failed to post digest source reply: {exc}")
        save_meta(date, {"tweet_id": root_id, "tweet_status": "ROOT_POSTED_REPLY_FAILED"})
        sys.exit(1)


if __name__ == "__main__":
    main()
