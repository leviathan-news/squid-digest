#!/usr/bin/env python3
"""
FALLBACK RECOVERY SCRIPT — rebuild Ghost blog posts from committed markdown source.

Use this when the Ghost MySQL database backup cannot be recovered.  It walks every
signals_YYYY-MM-DD.md in writeup/ and recreates the corresponding Ghost post with
status=published, tags=["digest","automated"], and the correct slug.

DO NOT run against a live Ghost instance that already has working posts — the
idempotency check (slug lookup before create) will skip existing slugs, but to be
safe this script is DRY-RUN by default.  Pass --apply to actually write to Ghost.

CRITICAL SAFETY: this script NEVER passes ?newsletter= or ?email_segment= query
parameters when creating posts.  Posts are created with status=published only;
Ghost will NOT queue an email blast for them.  Email sending requires an explicit
PUT with the newsletter/email_segment params (see ghost_client.send_email_to_members).
Omitting those params on POST /posts/ is the documented Ghost API behaviour for
"publish silently".  If you ever adapt this script to send email, you must
explicitly add those params — they are intentionally absent here.

Usage:
    # Dry run (default — no network writes, no Ghost API posts):
    python scripts/restore_rebuild_posts.py --dry-run --limit 5

    # Full dry run (prints all ~273 posts, zero writes):
    python scripts/restore_rebuild_posts.py --dry-run

    # Apply — actually creates posts in Ghost (requires GHOST_URL + GHOST_ADMIN_API_KEY):
    python scripts/restore_rebuild_posts.py --apply --limit 10

    # Date range:
    python scripts/restore_rebuild_posts.py --apply --since 2026-01-01 --until 2026-06-08
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Bootstrap: add src/ to sys.path so squid_digest imports work from the repo root.
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Load .env before anything that reads os.getenv
from dotenv import load_dotenv
load_dotenv(project_root / ".env")


# ---------------------------------------------------------------------------
# Slugify helper (used when meta has no published_ghost_url)
# ---------------------------------------------------------------------------

def _slugify_date(date: datetime) -> str:
    """Return the canonical Ghost slug for a date-only digest.

    Matches the pattern used by Ghost for titles like
    "🦑 Leviathan News Daily Digest - April 04, 2026"
    → leviathan-news-daily-digest-april-04-2026
    """
    month = date.strftime("%B").lower()   # e.g. "april"
    day = date.day                         # int, no zero-padding
    year = date.year
    return f"leviathan-news-daily-digest-{month}-{day}-{year}"


def _extract_slug_from_url(url: str) -> Optional[str]:
    """Parse the trailing slug from a published_ghost_url.

    e.g. https://digest.leviathannews.xyz/leviathan-news-daily-digest-april-04-2026/
    → leviathan-news-daily-digest-april-04-2026
    """
    url = url.rstrip("/")
    return url.rsplit("/", 1)[-1] if url else None


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def discover_digests(writeup_root: Path) -> list[dict]:
    """Walk writeup/ and return a sorted list of digest descriptors.

    Each descriptor:
        {
            "date":     datetime,
            "md_path":  Path,          # signals_YYYY-MM-DD.md
            "meta":     dict,          # contents of meta_YYYY-MM-DD.json (may be {})
        }
    """
    digests = []
    for md_path in sorted(writeup_root.rglob("signals_*.md")):
        # Extract date from filename: signals_2025-10-17.md → 2025-10-17
        stem = md_path.stem  # e.g. signals_2025-10-17
        date_str = stem.split("_", 1)[-1]
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            print(f"  WARNING: skipping unrecognised filename {md_path.name}", file=sys.stderr)
            continue

        # Load sidecar meta (gracefully; it may not exist for early dates)
        meta_path = md_path.parent / f"meta_{date_str}.json"
        meta: dict = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                print(f"  WARNING: could not parse {meta_path}: {exc}", file=sys.stderr)

        digests.append({"date": date, "md_path": md_path, "meta": meta})

    return digests


# ---------------------------------------------------------------------------
# Per-digest metadata derivation
# ---------------------------------------------------------------------------

def derive_post_fields(digest: dict) -> dict:
    """Return the Ghost post fields for one digest.

    Returns:
        {
            "title":        str,
            "slug":         str,
            "published_at": str (ISO-8601 UTC),
            "tags":         list[str],   # always ["digest", "automated"]
            "status":       str,         # always "published"
        }
    """
    date: datetime = digest["date"]
    meta: dict = digest["meta"]

    # Title: prefer meta title (the old naming is fine for archive), else use shared helper
    from squid_digest.config import get_digest_title
    title = meta.get("title") or get_digest_title(date)

    # Slug: parse from published URL if available, else synthesise from date
    published_url = meta.get("published_ghost_url", "")
    if published_url:
        slug = _extract_slug_from_url(published_url) or _slugify_date(date)
    else:
        slug = _slugify_date(date)

    # published_at: ISO-8601 UTC noon (Ghost requires timezone)
    published_at = date.strftime("%Y-%m-%dT12:00:00.000Z")

    return {
        "title": title,
        "slug": slug,
        "published_at": published_at,
        "tags": ["digest", "automated"],
        "status": "published",
    }


# ---------------------------------------------------------------------------
# Ghost interaction (only used in --apply mode)
# ---------------------------------------------------------------------------

def _ghost_slug_exists(client, slug: str) -> bool:
    """Return True if a post with this slug already exists in Ghost."""
    try:
        result = client._make_request("GET", f"posts/slug/{slug}/")
        return bool(result.get("posts"))
    except Exception as exc:
        # Ghost returns 404 as an error; treat as "does not exist"
        msg = str(exc).lower()
        if "404" in msg or "not found" in msg:
            return False
        # Any other error: re-raise so the caller can decide
        raise


def _create_ghost_post(client, fields: dict, html_content: str) -> dict:
    """Create a Ghost post with the given fields.

    IMPORTANT: We do NOT pass ?newsletter= or ?email_segment= query params.
    This means Ghost will publish the post without queueing any email blast.
    That is intentional — this script is for archive recovery only.
    """
    # Build mobiledoc wrapping the rendered HTML
    mobiledoc = client._html_to_mobiledoc(html_content)

    post_data = {
        "posts": [{
            "title": fields["title"],
            "slug": fields["slug"],
            "mobiledoc": mobiledoc,
            "status": fields["status"],          # "published"
            "published_at": fields["published_at"],
            # Tags: pass as name strings; Ghost creates them if absent
            "tags": [{"name": t} for t in fields["tags"]],
            # NO newsletter or email_segment — posts are created silently.
            # Omitting these params is the correct Ghost API behaviour for
            # "publish without sending email".  Do not add them.
        }]
    }

    # POST to /ghost/api/admin/posts/ with no query params
    # (ghost_client._make_request passes params= keyword — we deliberately
    # pass params=None here so no email-triggering query string is appended)
    response = client._make_request("POST", "posts/", data=post_data, params=None)
    return response.get("posts", [{}])[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recovery: rebuild Ghost digest posts from committed markdown source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="(DEFAULT) Parse files and print what would be created — zero network writes.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Actually create posts in Ghost (requires GHOST_URL + GHOST_ADMIN_API_KEY).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N digests (useful for testing).",
    )
    parser.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        default=None,
        help="Only process digests on or after this date.",
    )
    parser.add_argument(
        "--until",
        metavar="YYYY-MM-DD",
        default=None,
        help="Only process digests on or before this date.",
    )
    args = parser.parse_args()

    # --apply takes precedence; if neither flag is passed, we default to dry_run=True
    dry_run = not args.apply

    # Parse date filters
    since_dt: Optional[datetime] = None
    until_dt: Optional[datetime] = None
    if args.since:
        since_dt = datetime.strptime(args.since, "%Y-%m-%d")
    if args.until:
        until_dt = datetime.strptime(args.until, "%Y-%m-%d")

    # Discover all signal files
    writeup_root = project_root / "writeup"
    if not writeup_root.exists():
        print(f"ERROR: writeup directory not found at {writeup_root}", file=sys.stderr)
        sys.exit(1)

    all_digests = discover_digests(writeup_root)

    # Apply date filters
    if since_dt:
        all_digests = [d for d in all_digests if d["date"] >= since_dt]
    if until_dt:
        all_digests = [d for d in all_digests if d["date"] <= until_dt]

    # Apply limit
    if args.limit is not None:
        all_digests = all_digests[: args.limit]

    total = len(all_digests)
    print(f"{'DRY RUN — ' if dry_run else ''}Processing {total} digest(s) "
          f"({'no writes' if dry_run else 'LIVE WRITES to Ghost'})")
    print()

    # In --apply mode: initialise Ghost client (requires env vars)
    client = None
    if not dry_run:
        try:
            from squid_digest.email import GhostEmailClient
            client = GhostEmailClient()
            print(f"Ghost URL: {client.ghost_url}")
            print()
        except Exception as exc:
            print(f"ERROR: could not initialise Ghost client: {exc}", file=sys.stderr)
            print("Set GHOST_URL and GHOST_ADMIN_API_KEY in .env or environment.", file=sys.stderr)
            sys.exit(1)

    # We also need format_digest_html in --apply mode.  Import lazily so
    # dry-run never touches the network or requires Ghost env vars.
    if not dry_run:
        from squid_digest.email import GhostEmailClient  # noqa: already imported above

    n_created = 0
    n_skipped = 0
    n_errors = 0

    for i, digest in enumerate(all_digests, 1):
        date = digest["date"]
        md_path = digest["md_path"]
        fields = derive_post_fields(digest)

        print(f"[{i:3d}/{total}] {date.strftime('%Y-%m-%d')}  slug={fields['slug']}")
        print(f"         title='{fields['title']}'")

        if dry_run:
            # In dry-run we only read the file — zero network calls
            body_chars = len(md_path.read_text(encoding="utf-8"))
            print(f"         tags={fields['tags']}  status={fields['status']}")
            print(f"         body_chars={body_chars} (raw markdown, before HTML render)")
            print()
            n_created += 1   # "would create"
            continue

        # --- APPLY mode from here ---

        # 1. Idempotency: skip if slug already exists
        try:
            if _ghost_slug_exists(client, fields["slug"]):
                print(f"         SKIPPED (post with slug already exists in Ghost)")
                print()
                n_skipped += 1
                continue
        except Exception as exc:
            print(f"         ERROR checking slug: {exc}")
            n_errors += 1
            print()
            continue

        # 2. Render markdown → HTML
        try:
            md_content = md_path.read_text(encoding="utf-8")
            html_content = client.format_digest_html(md_content)
        except Exception as exc:
            print(f"         ERROR rendering markdown: {exc}")
            n_errors += 1
            print()
            continue

        # 3. Create the Ghost post (no email triggered — see _create_ghost_post docstring)
        try:
            post = _create_ghost_post(client, fields, html_content)
            post_id = post.get("id", "?")
            post_url = post.get("url", "?")
            print(f"         CREATED  id={post_id}  url={post_url}")
            n_created += 1
        except Exception as exc:
            print(f"         ERROR creating post: {exc}")
            n_errors += 1

        print()

    # Final summary
    print("=" * 60)
    if dry_run:
        print(f"DRY RUN: would create {n_created} posts "
              f"(idempotency checks skipped in dry-run — run --apply to check for existing slugs)")
    else:
        print(f"Created {n_created}, skipped {n_skipped} (slug exists), errors {n_errors}")
    print("=" * 60)


if __name__ == "__main__":
    main()
