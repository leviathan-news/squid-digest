#!/usr/bin/env python3
"""
Migration script to reorganize writeup folder into Year/Month/Day structure.

This script moves existing files from writeup/ to writeup/YYYY/MM/DD/
based on the date in the filename.

Usage:
    python scripts/migrate_writeup_structure.py --dry-run  # Preview changes
    python scripts/migrate_writeup_structure.py             # Actually migrate
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.config import WRITEUP_DIR, get_writeup_file_path


def extract_date_from_filename(filename: str) -> datetime | None:
    """
    Extract date from filename patterns like:
    - signals_2025-11-14.md
    - digest_2025-11-14.md
    - writeup_2025-11-14_id_12345.md
    - trading_signals_2025-11-14.md
    - backtest_results_2025-10-17_to_2025-11-03.md
    """
    # Pattern 1: signals_YYYY-MM-DD.md or digest_YYYY-MM-DD.md
    match = re.search(r'(signals|digest|writeup|trading_signals)_(\d{4}-\d{2}-\d{2})', filename)
    if match:
        try:
            return datetime.strptime(match.group(2), '%Y-%m-%d')
        except ValueError:
            pass
    
    # Pattern 2: backtest_results_YYYY-MM-DD_to_YYYY-MM-DD.md (use start date)
    match = re.search(r'backtest_results_(\d{4}-\d{2}-\d{2})_to_', filename)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
        except ValueError:
            pass
    
    # Pattern 3: Any file with YYYY-MM-DD pattern
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
        except ValueError:
            pass
    
    return None


def migrate_file(filepath: Path, dry_run: bool = False) -> tuple[bool, str]:
    """
    Migrate a single file to the new structure.
    
    Returns:
        (success, message)
    """
    filename = filepath.name
    
    # Skip files that should stay at root level
    if filename in ['portfolio_state.json']:
        return (True, f"Skipped (root-level file): {filename}")
    
    # Skip if already in a date directory structure
    parts = filepath.parts
    if len(parts) >= 4 and parts[-4] == 'writeup':
        # Check if it's already in YYYY/MM/DD structure
        try:
            year = int(parts[-3])
            month = int(parts[-2])
            day = int(parts[-1])
            # Validate it's a reasonable date
            if 2000 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return (True, f"Already in date structure: {filepath.relative_to(WRITEUP_DIR)}")
        except (ValueError, IndexError):
            pass
    
    # Extract date from filename
    file_date = extract_date_from_filename(filename)
    
    if not file_date:
        return (False, f"Cannot extract date from filename: {filename}")
    
    # Calculate destination path
    dest_path = get_writeup_file_path(filename, file_date)
    
    # Skip if source and destination are the same
    if filepath.resolve() == dest_path.resolve():
        return (True, f"Already in correct location: {dest_path.relative_to(WRITEUP_DIR)}")
    
    # Check if destination already exists
    if dest_path.exists():
        return (False, f"Destination already exists: {dest_path.relative_to(WRITEUP_DIR)}")
    
    if dry_run:
        return (True, f"Would move: {filepath.relative_to(WRITEUP_DIR)} -> {dest_path.relative_to(WRITEUP_DIR)}")
    
    # Actually move the file
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        filepath.rename(dest_path)
        return (True, f"Moved: {filepath.relative_to(WRITEUP_DIR)} -> {dest_path.relative_to(WRITEUP_DIR)}")
    except Exception as e:
        return (False, f"Error moving {filename}: {e}")


def migrate_thinking_logs(dry_run: bool = False) -> list[tuple[bool, str]]:
    """
    Migrate thinking_logs files to date-based structure.
    
    Files like: writeup/thinking_logs/signals_2025-11-14_thinking.log
    Should go to: writeup/2025/11/14/thinking_logs/signals_2025-11-14_thinking.log
    """
    results = []
    thinking_logs_dir = WRITEUP_DIR / "thinking_logs"
    
    if not thinking_logs_dir.exists():
        return results
    
    # Find all thinking log files
    for log_file in thinking_logs_dir.glob("*_thinking.log"):
        filename = log_file.name
        
        # Extract date from filename (e.g., signals_2025-11-14_thinking.log)
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if not match:
            results.append((False, f"Cannot extract date from: {filename}"))
            continue
        
        try:
            file_date = datetime.strptime(match.group(1), '%Y-%m-%d')
        except ValueError:
            results.append((False, f"Invalid date in: {filename}"))
            continue
        
        # Calculate destination path
        date_dir = WRITEUP_DIR / file_date.strftime("%Y") / file_date.strftime("%m") / file_date.strftime("%d")
        dest_dir = date_dir / "thinking_logs"
        dest_path = dest_dir / filename
        
        # Skip if already in correct location
        if log_file.resolve() == dest_path.resolve():
            results.append((True, f"Already in correct location: {dest_path.relative_to(WRITEUP_DIR)}"))
            continue
        
        # Check if destination already exists
        if dest_path.exists():
            results.append((False, f"Destination already exists: {dest_path.relative_to(WRITEUP_DIR)}"))
            continue
        
        if dry_run:
            results.append((True, f"Would move: {log_file.relative_to(WRITEUP_DIR)} -> {dest_path.relative_to(WRITEUP_DIR)}"))
        else:
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                log_file.rename(dest_path)
                results.append((True, f"Moved: {log_file.relative_to(WRITEUP_DIR)} -> {dest_path.relative_to(WRITEUP_DIR)}"))
            except Exception as e:
                results.append((False, f"Error moving {filename}: {e}"))
    
    # Remove empty thinking_logs directory if it exists
    if not dry_run and thinking_logs_dir.exists():
        try:
            if not any(thinking_logs_dir.iterdir()):
                thinking_logs_dir.rmdir()
                results.append((True, f"Removed empty directory: {thinking_logs_dir.relative_to(WRITEUP_DIR)}"))
        except Exception:
            pass  # Directory not empty or other error
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Migrate writeup folder to Year/Month/Day structure"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without actually moving files"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("WRITEUP FOLDER MIGRATION")
    print("=" * 80)
    print(f"Source directory: {WRITEUP_DIR.absolute()}")
    print(f"Mode: {'DRY RUN (preview only)' if args.dry_run else 'LIVE (will move files)'}")
    print()
    
    if not WRITEUP_DIR.exists():
        print(f"Error: Writeup directory does not exist: {WRITEUP_DIR}")
        sys.exit(1)
    
    # Find all files in writeup root (excluding subdirectories that are already date-based)
    files_to_migrate = []
    for item in WRITEUP_DIR.iterdir():
        if item.is_file():
            # Skip root-level files that should stay
            if item.name == 'portfolio_state.json':
                continue
            files_to_migrate.append(item)
        elif item.is_dir() and item.name == 'thinking_logs':
            # Handle thinking_logs separately
            continue
    
    print(f"Found {len(files_to_migrate)} files to migrate")
    print()
    
    # Migrate regular files
    results = []
    for filepath in sorted(files_to_migrate):
        success, message = migrate_file(filepath, dry_run=args.dry_run)
        results.append((success, message))
        status = "✓" if success else "✗"
        print(f"{status} {message}")
    
    # Migrate thinking logs
    print()
    print("Migrating thinking logs...")
    thinking_logs_results = migrate_thinking_logs(dry_run=args.dry_run)
    for success, message in thinking_logs_results:
        results.append((success, message))
        status = "✓" if success else "✗"
        print(f"{status} {message}")
    
    # Summary
    print()
    print("=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    
    successful = sum(1 for success, _ in results if success)
    failed = len(results) - successful
    
    print(f"Total files processed: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed/Skipped: {failed}")
    
    if failed > 0:
        print()
        print("Failed/Skipped items:")
        for success, message in results:
            if not success:
                print(f"  ✗ {message}")
    
    if args.dry_run:
        print()
        print("This was a DRY RUN. Run without --dry-run to actually migrate files.")
    
    print("=" * 80)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
