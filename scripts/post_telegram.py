#!/usr/bin/env python3
"""Manually post a signals digest to Telegram.

Usage:
    # Post yesterday's digest
    python scripts/post_telegram.py

    # Post a specific date
    python scripts/post_telegram.py --date 2025-11-16

    # Dry run (format but don't send)
    python scripts/post_telegram.py --date 2025-11-16 --dry-run
"""

import sys
import argparse
import traceback
from pathlib import Path
from datetime import datetime, timedelta

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.telegram import TelegramClient, format_for_telegram
from squid_digest.config import get_writeup_file_path


def main():
    parser = argparse.ArgumentParser(
        description="Post a signals digest to Telegram",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date in YYYY-MM-DD format (default: yesterday)",
        default=None
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to signals file (overrides --date)",
        default=None
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Format and validate but don't actually send"
    )
    
    args = parser.parse_args()
    
    # Determine which file to use
    if args.file:
        signals_path = Path(args.file)
    else:
        # Use date or default to yesterday
        if args.date:
            date_str = args.date
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
        else:
            yesterday = datetime.now() - timedelta(days=1)
            date_str = yesterday.strftime("%Y-%m-%d")
            file_date = yesterday
        
        signals_path = get_writeup_file_path(f"signals_{date_str}.md", file_date)
    
    # Validate file exists
    if not signals_path.exists():
        print(f"ERROR: Signals file not found: {signals_path}")
        print("\nAvailable signals files:")
        writeup_dir = Path(__file__).parent.parent / "writeup"
        if writeup_dir.exists():
            # Search recursively for signals files
            signals_files = sorted(writeup_dir.rglob("signals_*.md"))
            if signals_files:
                for f in signals_files[-10:]:  # Show last 10
                    print(f"  - {f.relative_to(writeup_dir)}")
            else:
                print("  (no signals files found)")
        sys.exit(1)
    
    print(f"Using signals file: {signals_path}")
    
    # Check if dry run
    if args.dry_run:
        print("DRY RUN MODE - Messages will not be sent\n")
    
    try:
        # Validate Telegram credentials (unless dry run)
        if not args.dry_run:
            import os
            if not os.getenv('TELEGRAM_BOT_TOKEN'):
                print('ERROR: TELEGRAM_BOT_TOKEN environment variable not set')
                print('Set it in your .env file or export it before running')
                sys.exit(1)
            if not os.getenv('TELEGRAM_CHANNEL_ID'):
                print('ERROR: TELEGRAM_CHANNEL_ID environment variable not set')
                print('Set it in your .env file or export it before running')
                sys.exit(1)
        
        # Read and validate content
        print(f"Reading signals file: {signals_path}")
        content = signals_path.read_text()
        
        if not content or len(content.strip()) == 0:
            print('ERROR: Signals file is empty')
            sys.exit(1)
        
        print(f"File size: {len(content)} characters")
        
        # Format content
        print('Formatting content for Telegram...')
        messages = format_for_telegram(content)
        
        if not messages or len(messages) == 0:
            print('ERROR: No messages generated from content')
            sys.exit(1)
        
        print(f'Formatted into {len(messages)} message(s)')
        
        # Validate message lengths
        print("\nMessage details:")
        for i, msg in enumerate(messages, 1):
            if len(msg) > 4096:
                print(f'  ⚠ Message {i}: {len(msg)} characters (EXCEEDS LIMIT!)')
            else:
                print(f'  ✓ Message {i}: {len(msg)} characters')
        
        # Preview first message (truncated)
        if messages:
            preview = messages[0][:200] + "..." if len(messages[0]) > 200 else messages[0]
            print(f"\nPreview of first message:\n{preview}\n")
        
        # Validate HTML structure for each message
        print("Validating HTML structure...")
        import re
        all_valid = True
        for i, msg in enumerate(messages, 1):
            # Check tag balance
            open_i = msg.count('<i>')
            close_i = msg.count('</i>')
            open_b = msg.count('<b>')
            close_b = msg.count('</b>')
            open_blockquote = msg.count('<blockquote>')
            close_blockquote = msg.count('</blockquote>')
            
            # Check tag nesting order
            tags = []
            for m in re.finditer(r'<(/?)(blockquote|i|b)>', msg):
                tags.append((m.start(), m.group(1) == '/', m.group(2)))
            
            # Validate nesting: check if closing tags are in correct order
            stack = []
            nesting_errors = []
            for pos, is_closing, tag_name in tags:
                if not is_closing:
                    stack.append((pos, tag_name))
                else:
                    if not stack:
                        nesting_errors.append(f"Closing </{tag_name}> at position {pos} has no opening tag")
                    else:
                        last_pos, last_tag = stack[-1]
                        if last_tag != tag_name:
                            nesting_errors.append(
                                f"Tag nesting error: Expected </{last_tag}> but found </{tag_name}> "
                                f"at position {pos} (last opened: <{last_tag}> at {last_pos})"
                            )
                        else:
                            stack.pop()
            
            if open_i != close_i or open_b != close_b or open_blockquote != close_blockquote:
                print(f"  ✗ Message {i}: Tag balance issues")
                if open_i != close_i:
                    print(f"    <i>: {open_i} open, {close_i} close")
                if open_b != close_b:
                    print(f"    <b>: {open_b} open, {close_b} close")
                if open_blockquote != close_blockquote:
                    print(f"    <blockquote>: {open_blockquote} open, {close_blockquote} close")
                all_valid = False
            
            if nesting_errors:
                print(f"  ✗ Message {i}: Tag nesting errors")
                for error in nesting_errors[:3]:  # Show first 3 errors
                    print(f"    {error}")
                all_valid = False
            
            if open_i == close_i and open_b == close_b and open_blockquote == close_blockquote and not nesting_errors:
                print(f"  ✓ Message {i}: HTML structure valid")
        
        if not all_valid:
            print("\n⚠ WARNING: HTML validation failed! Messages may not send correctly.")
            if args.dry_run:
                print("Fix the HTML issues before sending.")
            else:
                response = input("\nContinue anyway? (y/N): ")
                if response.lower() != 'y':
                    print("Aborted.")
                    sys.exit(1)
        
        # Send messages (or dry run)
        if args.dry_run:
            print("\nDRY RUN: Messages would be sent but are not being posted.")
            print("Remove --dry-run flag to actually send.")
            return
        
        # Initialize client and send
        print('Initializing Telegram client...')
        client = TelegramClient()
        
        print('Sending messages to Telegram...')
        results = client.send_multiple_messages(messages)
        
        # Report results
        success_count = sum(1 for r in results if r.get('ok', False))
        failed_count = len(messages) - success_count
        
        print("\n" + "=" * 80)
        if success_count == len(messages):
            print(f'✓ Successfully sent {success_count}/{len(messages)} message(s) to Telegram')
        else:
            print(f'⚠ Partially sent: {success_count}/{len(messages)} message(s) succeeded, {failed_count} failed')
            # Print error details for failed messages
            for i, result in enumerate(results, 1):
                if not result.get('ok', False):
                    print(f'  Message {i} failed: {result.get("error", "Unknown error")}')
            sys.exit(1)
        print("=" * 80)
        
    except Exception as e:
        print('=' * 80)
        print('ERROR posting to Telegram:')
        print(f'Exception type: {type(e).__name__}')
        print(f'Exception message: {str(e)}')
        print('=' * 80)
        print('Full traceback:')
        traceback.print_exc()
        print('=' * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
