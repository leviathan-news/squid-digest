#!/usr/bin/env python3
"""
CLI script for testing Telegram bot integration locally.

Usage:
    # Test with most recent signals file (dry run - preview only)
    python scripts/test_telegram.py --dry-run
    
    # Test with specific file (dry run)
    python scripts/test_telegram.py --digest-file writeup/signals_2025-11-03.md --dry-run
    
    # Actually send to Telegram
    python scripts/test_telegram.py --digest-file writeup/signals_2025-11-03.md
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path so we can import squid_digest
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

load_dotenv()

from squid_digest.telegram import TelegramClient, format_for_telegram


def main():
    parser = argparse.ArgumentParser(description="Test Telegram bot integration")
    parser.add_argument(
        "--digest-file",
        help="Path to the signals markdown file (default: most recent signals_*.md)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview formatted messages without sending to Telegram"
    )
    
    args = parser.parse_args()
    
    # Find signals file
    if args.digest_file:
        signals_path = Path(args.digest_file)
    else:
        # Find most recent signals file
        writeup_dir = Path(__file__).parent.parent / "writeup"
        signals_files = sorted(writeup_dir.glob("signals_*.md"), reverse=True)
        if not signals_files:
            print("Error: No signals files found in writeup/")
            sys.exit(1)
        signals_path = signals_files[0]
        print(f"Using most recent signals file: {signals_path}")
    
    if not signals_path.exists():
        print(f"Error: Signals file not found: {signals_path}")
        sys.exit(1)
    
    # Read and format content
    print(f"Reading signals file: {signals_path}")
    content = signals_path.read_text()
    
    print("Formatting for Telegram...")
    messages = format_for_telegram(content)
    
    print(f"\n✓ Formatted into {len(messages)} message(s)")
    print(f"  Message lengths: {[len(m) for m in messages]} characters")
    
    if args.dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN - Preview of formatted messages (not sending to Telegram)")
        print("=" * 80)
        
        for i, message in enumerate(messages, 1):
            print(f"\n--- Message {i}/{len(messages)} ({len(message)} chars) ---")
            print(message)
            print("-" * 80)
        
        print("\n✓ Dry run complete. Use without --dry-run to actually send to Telegram.")
    else:
        # Check credentials
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
        
        if not bot_token or not channel_id:
            print("Error: Telegram credentials not found in environment")
            print("Make sure TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID are set in .env")
            sys.exit(1)
        
        print(f"\nSending to Telegram channel: {channel_id}")
        
        try:
            client = TelegramClient()
            results = client.send_multiple_messages(messages)
            
            success_count = sum(1 for r in results if r.get('ok', False))
            failed_count = len(results) - success_count
            
            print(f"\n✓ Successfully sent {success_count}/{len(messages)} message(s)")
            
            if failed_count > 0:
                print(f"⚠ Failed to send {failed_count} message(s)")
                for i, result in enumerate(results, 1):
                    if not result.get('ok', False):
                        print(f"  Message {i}: {result.get('error', 'Unknown error')}")
            else:
                print("✓ All messages sent successfully!")
                
        except Exception as e:
            print(f"\n✗ Error sending to Telegram: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()

