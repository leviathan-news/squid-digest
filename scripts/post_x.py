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
import hashlib
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
from squid_digest.x.native import native_text as _native_text
from squid_digest.x.policy import assignment

NATIVE_DIGEST_ROOT_MAX_CHARS = 25_000


def _build_native_root(date: datetime, content: str, blurb: str) -> str:
    """Build a URL-free long-form root; never silently truncate editorial text."""
    title = f"\U0001f991 SQUID DIGEST \U0001f4f0 {date.strftime('%B %d, %Y')}"
    body = _native_text(content)
    if not body:
        raise ValueError('native digest body is empty')
    parts = [title, _native_text(blurb), body]
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
    parser.add_argument(
        "--force", action="store_true",
        help="legacy compatibility flag; durable delivery receipts are never bypassed",
    )
    args = parser.parse_args()

    date = datetime.strptime(args.date, "%Y-%m-%d")
    date_str = date.strftime("%Y-%m-%d")

    meta = load_meta(date)
    distribution = assignment(date.date(), meta)
    if not args.dry_run and meta.get('tweet_id') and meta.get('tweet_status') == 'ok':
        print(f"Digest distribution already complete (root={meta['tweet_id']})")
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
    # The legacy fallback concatenates three 60-character headline fragments.
    # X has room for the complete lead; never publish that clipped teaser.
    if blurb.startswith("In today's digest:"):
        blurb = meta.get("top_story_headline") or DEFAULT_BLURB

    # --- Build the URL-free root and its canonical-link reply ---
    try:
        root = _build_native_root(date, content, blurb)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        save_meta(date, {"tweet_status": "FAILED"})
        sys.exit(1)
    tracked_digest_url = _tracked_digest_url(digest_url)
    source_reply = _build_source_reply(digest_url)
    # Resume the exact payload, even if the source digest or renderer changed.
    root = distribution.get('root_text', root)
    source_reply = distribution.get('reply_text', source_reply)
    print(f"Native root ({len(root)} chars / {NATIVE_DIGEST_ROOT_MAX_CHARS}):")
    print(root)
    print(f"\nExperiment: {distribution['experiment'] or 'legacy'}; arm: {distribution['arm']}")
    if distribution['arm'] == 'linked_reply':
        print("\nFirst reply:")
        print(source_reply)
    else:
        print("\nNo outbound link or reply in this arm.")

    if args.dry_run:
        print("\n\u2713 Dry run complete. Remove --dry-run to post.")
        return

    def persist(**updates):
        distribution.update(updates)
        save_meta(date, {'x_distribution': distribution})

    persist(
        root_text=root, reply_text=source_reply,
        root_sha256=hashlib.sha256(root.encode()).hexdigest(),
        cost_basis='estimated_mdollars_not_vendor_billing',
    )

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
    if not root_id and username:
        existing = client.search_recent(
            _root_search_query(date, username), start_time=start_of_day.isoformat(),
        )
        # Search results are only evidence when the complete payload matches.
        matches = [row for row in existing if row.get('id') and row.get('text') == root]
        if len(matches) == 1:
            root_id = matches[0]['id']
            persist(root_state='confirmed', root_posted_at=matches[0].get('created_at'))
            save_meta(date, {"tweet_id": root_id, "tweet_status": "ROOT_POSTED"})
            print(f"\u23ed Native digest root already exists (id: {root_id})")
    print("\nPosting to X...")
    if not root_id:
        if distribution.get('root_state') in ('attempted', 'unknown'):
            raise RuntimeError('X root outcome is unproven; reconcile before retrying')
        persist(root_state='attempted', root_attempted_at=datetime.now(timezone.utc).isoformat())
        try:
            result = client.post_tweet(root)
            root_id = result.get("data", {}).get("id")
            if not root_id:
                raise RuntimeError(f"root post returned unexpected response: {result}")
            save_meta(date, {"tweet_id": root_id, "tweet_status": "ROOT_POSTED"})
            persist(root_state='confirmed', root_posted_at=datetime.now(timezone.utc).isoformat())
            print(f"\u2713 Native root posted: https://x.com/i/web/status/{root_id}")
        except Exception as exc:
            persist(root_state='unknown')
            print(f"\u2717 Failed to post native root: {exc}")
            save_meta(date, {"tweet_status": "FAILED"})
            sys.exit(1)

    if distribution['arm'] == 'no_link':
        persist(reply_state='not_applicable', estimated_delivery_mdollars=15)
        save_meta(date, {'tweet_id': root_id, 'tweet_status': 'ok'})
        print(f"Native no-link digest complete (root={root_id})")
        return

    if not reply_id and username:
        existing = client.search_recent(
            f'from:{username} url:"{tracked_digest_url}"',
            start_time=start_of_day.isoformat(),
        )
        reply = next((row for row in existing if any(
            ref.get('type') == 'replied_to' and str(ref.get('id')) == str(root_id)
            for ref in row.get('referenced_tweets', [])
        )), None)
        if reply and reply.get('id'):
            reply_id = reply['id']
            persist(reply_state='confirmed', reply_posted_at=reply.get('created_at'), estimated_delivery_mdollars=215)
            save_meta(date, {"tweet_reply_id": reply_id, "tweet_status": "ok"})
            print(f"\u23ed Digest source reply already exists (id: {reply_id})")

    if reply_id:
        print(f"\u23ed Digest distribution already complete (root={root_id}, reply={reply_id})")
        return

    if distribution.get('reply_state') in ('attempted', 'unknown'):
        raise RuntimeError('X reply outcome is unproven; reconcile before retrying')
    persist(reply_state='attempted', reply_attempted_at=datetime.now(timezone.utc).isoformat())
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
        persist(reply_state='confirmed', reply_posted_at=datetime.now(timezone.utc).isoformat(), estimated_delivery_mdollars=215)
        print(f"\u2713 Source reply posted: https://x.com/i/web/status/{reply_id}")
    except Exception as exc:
        persist(reply_state='unknown')
        print(f"\u2717 Failed to post digest source reply: {exc}")
        save_meta(date, {"tweet_id": root_id, "tweet_status": "ROOT_POSTED_REPLY_FAILED"})
        sys.exit(1)


if __name__ == "__main__":
    main()
