#!/usr/bin/env python3
"""
Retag Ghost posts: assign daily digests vs. other content to appropriate newsletters/tags.

Usage:
    # Dry run — list all posts and show proposed changes
    python scripts/retag_ghost_posts.py

    # Apply changes
    python scripts/retag_ghost_posts.py --apply
"""
import sys
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from squid_digest.email import GhostEmailClient


# Patterns that identify a daily digest post
DIGEST_PATTERNS = [
    r"Daily Digest",
    r"Leviathan News.*Digest",
    r"🦑",  # squid emoji in digest titles
]

DIGEST_TAG = "squid-digest"
UPDATES_TAG = "leviathan-updates"


def is_digest_post(post: dict) -> bool:
    """Determine if a post is a daily digest based on title and tags."""
    title = post.get("title", "")
    for pattern in DIGEST_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True
    # Also check existing tags
    tags = [t.get("slug", "") for t in post.get("tags", [])]
    if "digest" in tags or "automated" in tags:
        return True
    return False


def get_all_posts(client: GhostEmailClient) -> list:
    """Fetch all published posts from Ghost, paginating through results."""
    all_posts = []
    page = 1
    while True:
        result = client._make_request(
            "GET", "posts/",
            params={
                "limit": "50",
                "page": str(page),
                "include": "tags",
                "filter": "status:published",
            }
        )
        posts = result.get("posts", [])
        if not posts:
            break
        all_posts.extend(posts)
        meta = result.get("meta", {}).get("pagination", {})
        if page >= meta.get("pages", 1):
            break
        page += 1
    return all_posts


def retag_post(client: GhostEmailClient, post: dict, new_tag_slug: str, dry_run: bool = True) -> bool:
    """Add a tag to a post if it doesn't already have it."""
    existing_tags = post.get("tags", [])
    existing_slugs = {t.get("slug") for t in existing_tags}

    if new_tag_slug in existing_slugs:
        return False  # already tagged

    # Build updated tag list — keep existing, add new one
    updated_tags = [{"slug": t["slug"], "name": t["name"]} for t in existing_tags]
    # Ghost will auto-create the tag if it doesn't exist
    updated_tags.append({"slug": new_tag_slug, "name": new_tag_slug.replace("-", " ").title()})

    if dry_run:
        return True  # would change

    update_data = {
        "posts": [{
            "id": post["id"],
            "tags": updated_tags,
            "updated_at": post["updated_at"],
        }]
    }
    client._make_request("PUT", f"posts/{post['id']}/", data=update_data)
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Retag Ghost posts by newsletter category")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default: dry run)")
    args = parser.parse_args()

    dry_run = not args.apply

    try:
        client = GhostEmailClient()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("Fetching all published posts...")
    posts = get_all_posts(client)
    print(f"Found {len(posts)} published posts\n")

    digests = []
    updates = []

    for post in posts:
        title = post.get("title", "(untitled)")
        slug = post.get("slug", "")
        tags = [t.get("slug", "") for t in post.get("tags", [])]
        published = post.get("published_at", "")[:10]

        if is_digest_post(post):
            digests.append(post)
            category = "DIGEST"
        else:
            updates.append(post)
            category = "UPDATE"

        print(f"  [{category}] {published}  {title}")
        print(f"           tags: {', '.join(tags) or '(none)'}  slug: {slug}")

    print(f"\n--- Summary ---")
    print(f"Daily Digests:      {len(digests)}")
    print(f"Leviathan Updates:  {len(updates)}")

    # Now retag
    changes = 0

    print(f"\n--- Tagging digest posts with '{DIGEST_TAG}' ---")
    for post in digests:
        if retag_post(client, post, DIGEST_TAG, dry_run=dry_run):
            action = "would add" if dry_run else "added"
            print(f"  {action} '{DIGEST_TAG}' → {post['title'][:60]}")
            changes += 1

    print(f"\n--- Tagging non-digest posts with '{UPDATES_TAG}' ---")
    for post in updates:
        if retag_post(client, post, UPDATES_TAG, dry_run=dry_run):
            action = "would add" if dry_run else "added"
            print(f"  {action} '{UPDATES_TAG}' → {post['title'][:60]}")
            changes += 1

    if dry_run:
        print(f"\n🔍 DRY RUN: {changes} tag changes would be made. Run with --apply to execute.")
    else:
        print(f"\n✓ Applied {changes} tag changes.")


if __name__ == "__main__":
    main()
