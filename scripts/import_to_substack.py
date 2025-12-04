#!/usr/bin/env python3
"""
CLI script for importing RSS feed to Substack via browser automation.

This script automates the RSS import process on Substack's import page.
It supports dual authentication: session cookies (primary) and email/password (fallback).

Usage:
    python scripts/import_to_substack.py
    python scripts/import_to_substack.py --rss-url https://example.com/feed.xml
    python scripts/import_to_substack.py --substack-url https://yourpublication.substack.com
"""

import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path so we can import squid_digest
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

load_dotenv()

from squid_digest.email.substack_automation import SubstackAutomation


def main():
    parser = argparse.ArgumentParser(
        description="Import RSS feed to Substack via browser automation"
    )
    parser.add_argument(
        "--rss-url",
        default="https://raw.githubusercontent.com/leviathan-news/squid-digest/main/writeup/feed.xml",
        help="URL of the RSS feed to import (default: GitHub raw URL)"
    )
    parser.add_argument(
        "--substack-url",
        default=os.getenv("SUBSTACK_URL", "https://leviathannews.substack.com"),
        help="Base URL of your Substack publication"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)"
    )
    parser.add_argument(
        "--no-headless",
        action="store_false",
        dest="headless",
        help="Run browser in visible mode (for debugging)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60000,
        help="Page timeout in milliseconds (default: 60000)"
    )
    
    args = parser.parse_args()
    
    # Get credentials from environment variables
    session_cookies_json = os.getenv("SUBSTACK_SESSION_COOKIES")
    substack_email = os.getenv("SUBSTACK_EMAIL")
    substack_password = os.getenv("SUBSTACK_PASSWORD")
    
    # Validate that we have at least one authentication method
    if not session_cookies_json and not (substack_email and substack_password):
        print("❌ ERROR: No authentication method configured!")
        print("")
        print("Please set one of the following:")
        print("  1. SUBSTACK_SESSION_COOKIES (JSON string with cookies array)")
        print("  2. SUBSTACK_EMAIL and SUBSTACK_PASSWORD (for fallback login)")
        print("")
        print("For GitHub Actions, add these as repository secrets.")
        sys.exit(1)
    
    print("=" * 80)
    print("Substack RSS Import Automation")
    print("=" * 80)
    print(f"RSS Feed URL: {args.rss_url}")
    print(f"Substack URL: {args.substack_url}")
    print(f"Headless mode: {args.headless}")
    print("")
    
    # Initialize automation
    automation = SubstackAutomation(
        substack_url=args.substack_url,
        headless=args.headless,
        timeout=args.timeout
    )
    
    try:
        # Start browser
        print("Starting browser...")
        automation.start()
        
        # Try cookie authentication first (if available)
        authenticated = False
        if session_cookies_json:
            print("Attempting cookie authentication...")
            authenticated = automation.authenticate_with_cookies(session_cookies_json)
        
        # Fall back to email/password if cookies failed
        if not authenticated and substack_email and substack_password:
            print("Cookie authentication failed, trying email/password login...")
            authenticated = automation.authenticate_with_login(
                substack_email,
                substack_password
            )
        
        if not authenticated:
            print("❌ Authentication failed with all available methods")
            sys.exit(1)
        
        # Perform RSS import
        print("")
        print("Starting RSS feed import...")
        success = automation.import_rss_feed(args.rss_url)
        
        if success:
            print("")
            print("=" * 80)
            print("✓ RSS feed import completed successfully!")
            print("=" * 80)
            sys.exit(0)
        else:
            print("")
            print("=" * 80)
            print("❌ RSS feed import failed")
            print("=" * 80)
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Always cleanup
        automation.stop()
        print("\nBrowser closed.")


if __name__ == "__main__":
    main()

