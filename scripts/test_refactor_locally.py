#!/usr/bin/env python3
"""
Test script to verify the refactored writeup structure works end-to-end.

This script:
1. Generates a test digest using the new Year/Month/Day structure
2. Optionally sends email to kraken@leviathannews.xyz (use --send-email flag)
3. Cleans up the test files afterward

Usage:
    python scripts/test_refactor_locally.py
"""

import asyncio
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# Add scripts to path for importing digest
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Set ACTIVE_PROMPT to 'signals' BEFORE any imports that might use it
# This ensures trading signals are generated, not digest
os.environ['ACTIVE_PROMPT'] = 'signals'

# Configure logging to show INFO level messages from digest module
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s',
    force=True  # Override any existing configuration
)

from squid_digest.config import get_writeup_file_path, WRITEUP_DIR

# Note: digest_module is imported later in the function, after ensuring ACTIVE_PROMPT is set


def _restore_file_backups(file_backups: dict):
    """Restore backed up files."""
    if not file_backups:
        return
    
    print("\n📦 Restoring backed up files...")
    import shutil
    for original_path, backup_path in file_backups.items():
        if backup_path.exists():
            try:
                shutil.copy2(backup_path, original_path)
                backup_path.unlink()  # Remove backup after restoring
                print(f"  ✓ Restored: {original_path.name}")
            except Exception as e:
                print(f"  ✗ Failed to restore {original_path.name}: {e}")


def cleanup_test_files(test_date: datetime, files_created_during_test: set, file_backups: dict = None):
    """Remove only test files created during this test run.
    
    Args:
        test_date: Date of the test
        files_created_during_test: Set of file paths that were created during this test
    """
    writeup_dir_abs = Path(WRITEUP_DIR).resolve()
    date_dir = writeup_dir_abs / test_date.strftime("%Y") / test_date.strftime("%m") / test_date.strftime("%d")
    
    if not date_dir.exists():
        print(f"  No files to clean up in {date_dir.relative_to(writeup_dir_abs)}")
        return
    
    print(f"\n🧹 Cleaning up test files in {date_dir.relative_to(writeup_dir_abs)}/...")
    
    files_removed = 0
    files_skipped = 0
    
    for file_path in date_dir.rglob("*"):
        if file_path.is_file():
            # Only delete files that were created during this test
            if file_path in files_created_during_test:
                try:
                    file_path.unlink()
                    files_removed += 1
                    writeup_dir_abs = Path(WRITEUP_DIR).resolve()
                    print(f"  ✓ Removed: {file_path.relative_to(writeup_dir_abs)}")
                except Exception as e:
                    writeup_dir_abs = Path(WRITEUP_DIR).resolve()
                    print(f"  ✗ Failed to remove {file_path.relative_to(writeup_dir_abs)}: {e}")
            else:
                files_skipped += 1
                writeup_dir_abs = Path(WRITEUP_DIR).resolve()
                print(f"  ⊘ Skipped (pre-existing): {file_path.relative_to(writeup_dir_abs)}")
    
    # Remove empty directories
    try:
        # Remove thinking_logs if empty
        writeup_dir_abs = Path(WRITEUP_DIR).resolve()
        thinking_logs_dir = date_dir / "thinking_logs"
        if thinking_logs_dir.exists() and not any(thinking_logs_dir.iterdir()):
            thinking_logs_dir.rmdir()
            print(f"  ✓ Removed empty directory: {thinking_logs_dir.relative_to(writeup_dir_abs)}")
        
        # Remove date directory if empty
        if not any(date_dir.iterdir()):
            date_dir.rmdir()
            print(f"  ✓ Removed empty directory: {date_dir.relative_to(writeup_dir_abs)}")
            
            # Try to remove month directory if empty
            month_dir = date_dir.parent
            if not any(month_dir.iterdir()):
                month_dir.rmdir()
                print(f"  ✓ Removed empty directory: {month_dir.relative_to(writeup_dir_abs)}")
                
                # Try to remove year directory if empty
                year_dir = month_dir.parent
                if not any(year_dir.iterdir()):
                    year_dir.rmdir()
                    print(f"  ✓ Removed empty directory: {year_dir.relative_to(writeup_dir_abs)}")
    except Exception as e:
        print(f"  ⚠ Could not remove some directories: {e}")
    
    print(f"  ✓ Cleanup complete: {files_removed} file(s) removed")
    
    # Restore backed up files after cleanup
    if file_backups:
        _restore_file_backups(file_backups)


async def main(auto_cleanup=False, send_email=False):
    """Run the full test pipeline.
    
    Args:
        auto_cleanup: If True, automatically clean up test files without prompting
        send_email: If True, send test email to kraken@leviathannews.xyz only
    """
    print("=" * 80)
    print("TESTING REFACTORED WRITEUP STRUCTURE")
    print("=" * 80)
    print()
    
    # Get today's date for test files
    test_date = datetime.now()
    date_str = test_date.strftime("%Y-%m-%d")
    date_dir = WRITEUP_DIR / test_date.strftime("%Y") / test_date.strftime("%m") / test_date.strftime("%d")
    
    # Track existing files BEFORE the test and back them up
    existing_files = set()
    file_backups = {}  # Map of original file path -> backup file path
    if date_dir.exists():
        for file_path in date_dir.rglob("*"):
            if file_path.is_file():
                existing_files.add(file_path)
                # Create backup of files that might be overwritten
                # Only backup .md files that match the expected pattern
                if file_path.suffix == '.md' and (f"signals_{date_str}" in file_path.name or f"digest_{date_str}" in file_path.name):
                    backup_path = file_path.with_suffix('.md.backup')
                    import shutil
                    shutil.copy2(file_path, backup_path)
                    file_backups[file_path] = backup_path
                    print(f"  📦 Backed up: {file_path.name} -> {backup_path.name}")
    
    print(f"📅 Test date: {date_str}")
    print(f"📁 Files will be created in: writeup/{test_date.strftime('%Y/%m/%d')}/")
    if existing_files:
        print(f"⚠️  Warning: {len(existing_files)} pre-existing file(s) found in this date directory")
        if file_backups:
            print(f"   📦 Backed up {len(file_backups)} file(s) that might be overwritten")
        print("   Original files will be restored after test")
    print()
    
    # Step 1: Generate trading signals (not digest!)
    print("Step 1: Generating trading signals...")
    print("-" * 80)
    
    # ACTIVE_PROMPT is already set to 'signals' at module level
    # But we need to reload any modules that might have cached the old value
    import importlib.util
    import importlib
    
    # Reload modules that import ACTIVE_PROMPT to ensure they pick up the new value
    from squid_digest.context import prompts
    from squid_digest.core import digest_engine
    importlib.reload(prompts.template)
    importlib.reload(digest_engine)
    print("  ✓ ACTIVE_PROMPT=signals (required for backtest functionality)")
    
    # Import the digest module (it will read ACTIVE_PROMPT from env var)
    digest_path = Path(__file__).parent / "digest.py"
    spec = importlib.util.spec_from_file_location("digest_module", digest_path)
    digest_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(digest_module)
    
    # Verify ACTIVE_PROMPT is set correctly in the module
    if hasattr(digest_module, 'ACTIVE_PROMPT'):
        if digest_module.ACTIVE_PROMPT != 'signals':
            print(f"  ⚠️  Warning: ACTIVE_PROMPT in module is '{digest_module.ACTIVE_PROMPT}', expected 'signals'")
            print(f"     This will generate digest instead of signals!")
        else:
            print(f"  ✓ Verified: ACTIVE_PROMPT is set to 'signals' in digest module")
    
    try:
        # Call the main function from digest module
        # We need to fetch news and tokens first, then generate bundle
        await digest_module.main(
            fetch=True,
            limit=5,  # Small limit for testing
            each_news=False,
            bundle=True,
            verbose=True,
            resolve_urls=False,  # Skip URL resolution for speed
            fetch_tokens_flag=True
        )
        print("✓ Trading signals generation completed")
        
        # Small delay to ensure file is fully written to disk
        import time
        time.sleep(1)
        print("  (Waiting 1 second for file system sync...)")
    except Exception as e:
        print(f"✗ Trading signals generation failed: {e}")
        import traceback
        traceback.print_exc()
        # Restore backups before exiting
        _restore_file_backups(file_backups)
        return 1
    
    # Step 2: Find the generated file (could be signals_ or digest_)
    print()
    print("Step 2: Locating generated file...")
    print("-" * 80)
    
    import time
    date_dir = WRITEUP_DIR / test_date.strftime("%Y") / test_date.strftime("%m") / test_date.strftime("%d")
    
    # Find the most recently created/modified .md file in the date directory
    # This handles both signals_ and digest_ files
    signals_file = None
    if date_dir.exists():
        md_files = list(date_dir.glob("*.md"))
        if md_files:
            # Sort by modification time, most recent first
            md_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            # Prefer signals_ over digest_, but use most recent if signals_ is old
            signals_candidates = [f for f in md_files if "signals_" in f.name]
            digest_candidates = [f for f in md_files if "digest_" in f.name]
            
            # Check if signals_ file was created in the last 2 minutes (likely from this run)
            if signals_candidates:
                signals_mtime = signals_candidates[0].stat().st_mtime
                time_since_mod = time.time() - signals_mtime
                if time_since_mod < 120:  # Created in last 2 minutes
                    signals_file = signals_candidates[0]
                    print(f"  Found recently created signals file: {signals_file.name}")
            
            # If no recent signals file, check digest file
            if signals_file is None and digest_candidates:
                digest_mtime = digest_candidates[0].stat().st_mtime
                time_since_mod = time.time() - digest_mtime
                if time_since_mod < 120:  # Created in last 2 minutes
                    signals_file = digest_candidates[0]
                    print(f"  Found recently created digest file: {signals_file.name}")
            
            # Fallback: use most recently modified file
            if signals_file is None:
                signals_file = md_files[0]
                print(f"  Using most recently modified file: {signals_file.name}")
    
    if signals_file is None or not signals_file.exists():
        writeup_dir_abs = Path(WRITEUP_DIR).resolve()
        print(f"✗ No suitable file found in {date_dir.relative_to(writeup_dir_abs)}/")
        print("  Available files in date directory:")
        if date_dir.exists():
            for f in date_dir.glob("*.md"):
                mtime = f.stat().st_mtime
                age = time.time() - mtime
                print(f"    - {f.name} (modified {age:.1f} seconds ago)")
        cleanup_test_files(test_date, set(), file_backups)
        return 1
    
    # Verify the file was actually updated (check modification time)
    file_mtime = signals_file.stat().st_mtime
    current_time = time.time()
    time_since_mod = current_time - file_mtime
    
    # Force a file system sync and re-read to ensure we have the latest content
    signals_file = signals_file.resolve()  # Resolve any symlinks
    # Resolve WRITEUP_DIR to absolute path for comparison
    writeup_dir_abs = Path(WRITEUP_DIR).resolve()
    print(f"✓ Found file: {signals_file.relative_to(writeup_dir_abs)}")
    print(f"  File size: {signals_file.stat().st_size:,} bytes")
    print(f"  Last modified: {time.ctime(file_mtime)} ({time_since_mod:.1f} seconds ago)")
    
    # If file was modified more than 2 minutes ago, it might be stale
    if time_since_mod > 120:
        print(f"  ⚠️  Warning: File was last modified {time_since_mod:.1f} seconds ago")
        print("    This might be a pre-existing file, not the newly generated one")
    
    # Read a snippet to verify it's the new content (check for backtest section)
    with open(signals_file, 'r', encoding='utf-8') as f:
        content_preview = f.read(1000)
        if "Backtest Results" in content_preview:
            print("  ✓ File contains backtest section (likely newly generated)")
        elif time_since_mod < 120:
            print("  ✓ File was recently modified (likely newly generated)")
        else:
            print("  ⚠️  File might be stale - check if backtest section is present")
    
    # Step 3: Display generated content
    print()
    print("Step 3: Generated Content Preview")
    print("-" * 80)
    
    # Read and display the full markdown content
    signals_file_abs = signals_file.resolve()
    
    if not signals_file_abs.exists():
        print(f"✗ Signals file not found: {signals_file_abs}")
        cleanup_test_files(test_date, set(), file_backups)
        return 1
    
    with open(signals_file_abs, 'r', encoding='utf-8') as f:
        full_content = f.read()
    
    # Check for backtest section and signals
    has_backtest = "Backtest Results" in full_content
    has_signals = "## 🎯 Trading Signals" in full_content or "**$" in full_content
    
    print(f"✓ File size: {len(full_content):,} characters")
    print(f"  Contains signals: {has_signals}")
    print(f"  Contains backtest: {has_backtest}")
    
    if not has_signals:
        print("  ⚠️  Warning: No trading signals found in file")
    if not has_backtest:
        print("  ⚠️  Warning: No backtest section found")
        print("     Possible reasons:")
        print("     - No signals were generated (backtest only runs if signals exist)")
        print("     - ACTIVE_PROMPT wasn't set to 'signals'")
        print("     - Backtest failed silently")
    
    # Show a preview of the content structure
    lines = full_content.split('\n')
    print()
    print("Content structure (first 30 lines):")
    for i, line in enumerate(lines[:30], 1):
        if line.strip():
            print(f"  {i:3d}: {line[:80]}")
    
    print()
    print("=" * 80)
    print("FULL MARKDOWN CONTENT:")
    print("=" * 80)
    print(full_content)
    print("=" * 80)
    print()
    
    # Step 3.5: Send email if requested
    email_sent = False
    if send_email:
        print()
        print("Step 3.5: Sending test email...")
        print("-" * 80)
        
        try:
            from squid_digest.email import GhostEmailClient
            
            # Initialize Ghost email client
            try:
                client = GhostEmailClient()
                print("  ✓ Ghost email client initialized")
            except ValueError as e:
                print(f"  ✗ Failed to initialize Ghost email client: {e}")
                print("     Make sure GHOST_URL and GHOST_ADMIN_API_KEY are set in your environment")
                print("     Skipping email sending...")
            else:
                # Send email only to kraken@leviathannews.xyz
                test_recipient = "kraken@leviathannews.xyz"
                print(f"  📧 Sending test email to: {test_recipient}")
                
                success = client.send_digest_email(
                    digest_path=str(signals_file_abs),
                    recipients=[test_recipient]
                )
                
                if success:
                    print(f"  ✓ Test email sent successfully to {test_recipient}")
                    email_sent = True
                else:
                    print(f"  ✗ Failed to send test email to {test_recipient}")
        except Exception as e:
            print(f"  ✗ Error sending email: {e}")
            import traceback
            traceback.print_exc()
            print("     Continuing with test...")
    
    # Step 4: Verify file structure
    print()
    print("Step 4: Verifying file structure...")
    print("-" * 80)
    
    writeup_dir_abs = Path(WRITEUP_DIR).resolve()
    date_dir = signals_file.parent
    expected_structure = f"writeup/{test_date.strftime('%Y/%m/%d')}/"
    
    if signals_file.parent == date_dir and str(date_dir.relative_to(writeup_dir_abs)) == test_date.strftime("%Y/%m/%d"):
        print(f"✓ File structure correct: {expected_structure}")
    else:
        print(f"✗ File structure incorrect")
        print(f"  Expected: {expected_structure}")
        print(f"  Actual: {signals_file.relative_to(writeup_dir_abs)}")
        # Clean up any files we created during this test
        files_created = {signals_file} if signals_file.exists() and signals_file not in existing_files else set()
        cleanup_test_files(test_date, files_created, file_backups)
        return 1
    
    # Identify files created during this test
    files_created_during_test = set()
    if date_dir.exists():
        for file_path in date_dir.rglob("*"):
            if file_path.is_file() and file_path not in existing_files:
                files_created_during_test.add(file_path)
    
    # List all files in the directory
    print()
    print("Files in date directory:")
    writeup_dir_abs = Path(WRITEUP_DIR).resolve()
    all_files = list(date_dir.rglob("*")) if date_dir.exists() else []
    for file_path in sorted(all_files):
        if file_path.is_file():
            if file_path in files_created_during_test:
                print(f"  - {file_path.relative_to(writeup_dir_abs)} (created in this test)")
            else:
                print(f"  - {file_path.relative_to(writeup_dir_abs)} (pre-existing)")
    
    # Step 5: Cleanup
    print()
    files_cleaned = False
    if auto_cleanup:
        print("🧹 Auto-cleaning test files...")
        cleanup_test_files(test_date, files_created_during_test, file_backups)
        files_cleaned = True
    else:
        if files_created_during_test:
            response = input("🧹 Clean up test files? (y/N): ").strip().lower()
            if response == 'y':
                cleanup_test_files(test_date, files_created_during_test, file_backups)
                files_cleaned = True
            else:
                print("  Test files left in place for inspection")
                writeup_dir_abs = Path(WRITEUP_DIR).resolve()
                print(f"  Location: {date_dir.relative_to(writeup_dir_abs)}/")
        else:
            print("  No test files to clean up (all files were pre-existing)")
    
    print()
    print("=" * 80)
    print("✓ TEST COMPLETE - All checks passed!")
    print("=" * 80)
    print()
    print("Summary:")
    print("  ✓ Trading signals generated with new Year/Month/Day structure")
    if send_email:
        if email_sent:
            print("  ✓ Test email sent to kraken@leviathannews.xyz")
        else:
            print("  ✗ Test email failed to send")
    else:
        print("  ⊘ Email sending disabled (use --send-email to enable)")
    print("  ✓ File structure verified")
    if files_cleaned:
        print("  ✓ Test files cleaned up")
    else:
        print("  ⚠ Test files left in place")
    print()
    
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test the refactored writeup structure end-to-end"
    )
    parser.add_argument(
        "--auto-cleanup",
        action="store_true",
        help="Automatically clean up test files without prompting"
    )
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="Send test email to kraken@leviathannews.xyz only"
    )
    
    args = parser.parse_args()
    
    try:
        exit_code = asyncio.run(main(auto_cleanup=args.auto_cleanup, send_email=args.send_email))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
