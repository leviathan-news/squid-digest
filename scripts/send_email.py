#!/usr/bin/env python3
"""
CLI script for sending emails via Squid Digest Ghost email service.

Usage:
    python scripts/send_email.py --type admin --digest-file writeup/trading_signals_2025-01-15.md
    python scripts/send_email.py --type public --digest-file writeup/trading_signals_2025-01-15.md
    python scripts/send_email.py --type edit --digest-file writeup/trading_signals_2025-01-15.md --github-url https://github.com/user/repo/blob/main/writeup/file.md
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path so we can import squid_digest
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

load_dotenv()

from squid_digest.email import GhostEmailClient


def main():
    parser = argparse.ArgumentParser(description="Send emails via Squid Digest Ghost email service")
    parser.add_argument(
        "--type", 
        choices=["admin", "public", "edit"], 
        required=True,
        help="Type of email to send"
    )
    parser.add_argument(
        "--digest-file", 
        required=True,
        help="Path to the digest markdown file"
    )
    parser.add_argument(
        "--github-url",
        help="GitHub URL to the digest file (required for admin and edit types)"
    )
    parser.add_argument(
        "--changes-summary",
        help="Summary of changes made (for edit type)"
    )
    parser.add_argument(
        "--recipients",
        help="Comma-separated list of recipient emails (overrides env vars)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be sent without actually sending"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.type in ["admin", "edit"] and not args.github_url:
        print("Error: --github-url is required for admin and edit email types")
        sys.exit(1)
    
    digest_file = Path(args.digest_file)
    if not digest_file.exists():
        print(f"Error: Digest file not found: {args.digest_file}")
        sys.exit(1)
    
    # Initialize Ghost email client
    try:
        client = GhostEmailClient()
    except ValueError as e:
        print(f"Error: {e}")
        print("Make sure GHOST_URL and GHOST_ADMIN_API_KEY are set in your environment or .env file")
        sys.exit(1)
    
    # Handle dry run
    if args.dry_run:
        print("DRY RUN MODE - No emails will be sent")
        print(f"Email type: {args.type}")
        print(f"Digest file: {args.digest_file}")
        if args.github_url:
            print(f"GitHub URL: {args.github_url}")
        if args.changes_summary:
            print(f"Changes summary: {args.changes_summary}")
        if args.recipients:
            print(f"Recipients: {args.recipients}")
        else:
            if args.type == "admin":
                print(f"Admin emails: {os.getenv('ADMIN_EMAILS', 'ghall1@gmail.com')}")
            else:
                print(f"Public emails: {os.getenv('PUBLIC_EMAILS', 'ghall1@gmail.com,curvedefi@gmail.com')}")
        print(f"Ghost URL: {client.ghost_url}")
        return
    
    # Send email based on type
    success = False
    
    if args.type == "admin":
        success = client.send_admin_notification(
            digest_path=str(digest_file),
            github_url=args.github_url,
            is_edit=False
        )
        
    elif args.type == "public":
        recipients = None
        if args.recipients:
            recipients = [email.strip() for email in args.recipients.split(",")]
        
        success = client.send_digest_email(
            digest_path=str(digest_file),
            recipients=recipients
        )
        
    elif args.type == "edit":
        success = client.send_edit_notification(
            digest_path=str(digest_file),
            github_url=args.github_url,
            changes_summary=args.changes_summary or ""
        )
    
    if success:
        print(f"✓ {args.type.title()} email sent successfully via Ghost")
    else:
        print(f"✗ Failed to send {args.type} email via Ghost")
        sys.exit(1)


if __name__ == "__main__":
    main()