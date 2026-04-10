#!/usr/bin/env python3
"""
Import Substack subscribers into Ghost, subscribed only to a specific newsletter.

Usage:
    # Dry run — show what would be imported
    python scripts/import_substack_subscribers.py /path/to/subscriber-export.csv

    # Import into "leviathan-updates" newsletter only
    python scripts/import_substack_subscribers.py /path/to/subscriber-export.csv --apply

    # Import into a different newsletter
    python scripts/import_substack_subscribers.py /path/to/subscriber-export.csv --apply --newsletter squid-digest
"""
import csv
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from squid_digest.email import GhostEmailClient


def get_newsletter_by_slug(client: GhostEmailClient, slug: str) -> dict:
    """Fetch a newsletter by slug."""
    result = client._make_request("GET", "newsletters/")
    for nl in result.get("newsletters", []):
        if nl.get("slug") == slug:
            return nl
    return None


def import_subscribers(csv_path: str, newsletter_slug: str = "leviathan-updates", dry_run: bool = True):
    client = GhostEmailClient()

    # Look up the target newsletter
    newsletter = get_newsletter_by_slug(client, newsletter_slug)
    if not newsletter:
        available = client._make_request("GET", "newsletters/")
        slugs = [nl.get("slug") for nl in available.get("newsletters", [])]
        print(f"Error: newsletter '{newsletter_slug}' not found. Available: {slugs}")
        sys.exit(1)

    newsletter_id = newsletter["id"]
    newsletter_name = newsletter["name"]
    print(f"Target newsletter: {newsletter_name} (slug: {newsletter_slug}, id: {newsletter_id})")

    # Parse CSV
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"Error: file not found: {csv_path}")
        sys.exit(1)

    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} subscribers in CSV\n")

    created = 0
    updated = 0
    skipped = 0
    errors = 0

    for i, row in enumerate(rows, 1):
        email = row.get("Email", "").strip()
        name = row.get("Name", "").strip() or None

        if not email:
            skipped += 1
            continue

        if dry_run:
            print(f"  [{i}/{len(rows)}] would import: {email}" + (f" ({name})" if name else ""))
            created += 1
            continue

        try:
            # Check if member already exists
            existing = client.get_members(f"email:{email}")

            if existing:
                member = existing[0]
                member_id = member["id"]
                # Check if already subscribed to this newsletter
                current_newsletters = member.get("newsletters", [])
                current_nl_ids = {nl.get("id") for nl in current_newsletters}

                if newsletter_id in current_nl_ids:
                    print(f"  [{i}/{len(rows)}] already subscribed: {email}")
                    skipped += 1
                    continue

                # Add this newsletter to their existing subscriptions
                updated_newsletters = [{"id": nl["id"]} for nl in current_newsletters]
                updated_newsletters.append({"id": newsletter_id})

                update_data = {
                    "members": [{
                        "id": member_id,
                        "newsletters": updated_newsletters,
                    }]
                }
                client._make_request("PUT", f"members/{member_id}/", data=update_data)
                print(f"  [{i}/{len(rows)}] added newsletter: {email}")
                updated += 1

            else:
                # Create new member subscribed ONLY to the target newsletter
                member_data = {
                    "members": [{
                        "email": email,
                        "name": name or email.split("@")[0],
                        "labels": [{"name": "substack-import"}],
                        "newsletters": [{"id": newsletter_id}],
                    }]
                }
                client._make_request("POST", "members/", data=member_data)
                print(f"  [{i}/{len(rows)}] created: {email}" + (f" ({name})" if name else ""))
                created += 1

        except Exception as e:
            print(f"  [{i}/{len(rows)}] ERROR {email}: {e}")
            errors += 1

    print(f"\n--- Summary ---")
    if dry_run:
        print(f"DRY RUN: {created} members would be imported into '{newsletter_name}'")
    else:
        print(f"Created:  {created}")
        print(f"Updated:  {updated} (added newsletter subscription)")
        print(f"Skipped:  {skipped} (already subscribed or empty)")
        print(f"Errors:   {errors}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import Substack subscribers into Ghost newsletter")
    parser.add_argument("csv_file", help="Path to Substack subscriber export CSV")
    parser.add_argument("--apply", action="store_true", help="Actually import (default: dry run)")
    parser.add_argument("--newsletter", default="leviathan-updates",
                        help="Ghost newsletter slug to subscribe to (default: leviathan-updates)")
    args = parser.parse_args()

    import_subscribers(args.csv_file, newsletter_slug=args.newsletter, dry_run=not args.apply)
