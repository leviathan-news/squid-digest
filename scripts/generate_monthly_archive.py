#!/usr/bin/env python3
"""
Generate monthly archive README files for writeup directories.

This script:
1. Finds all signals files in a given month directory
2. Extracts headlines and formats them
3. Creates/updates README.md in the month directory

Usage:
    python scripts/generate_monthly_archive.py --year 2025 --month 11
    python scripts/generate_monthly_archive.py --year 2025 --month 10
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple


def extract_first_headline(signals_file: Path) -> Optional[str]:
    """Extract the first (top) headline from a signals file."""
    try:
        content = signals_file.read_text()
    except Exception:
        return None
    
    headlines = []
    top_stories_match = re.search(r'## 🔥 Top Stories(.+?)(?=##|$)', content, re.DOTALL)
    if not top_stories_match:
        return None

    top_stories_content = top_stories_match.group(1)
    
    # Pattern 1: <strong><a href="...">N. HEADLINE</a></strong> (headline inside link)
    # Pattern 2: <strong>N. HEADLINE</strong> (headline directly in strong tag)
    pattern1 = r'<strong[^>]*><a[^>]*>(\d+)\.\s*([^<]+)</a></strong>'
    pattern2 = r'<strong[^>]*>(\d+)\.\s*([^<]+)</strong>'
    
    matches = re.findall(pattern1, top_stories_content)
    if not matches:
        matches = re.findall(pattern2, top_stories_content)

    if matches:
        headline = matches[0][1].strip()
        return headline
    return None


def extract_source_info(signals_file: Path) -> Optional[Tuple[str, str]]:
    """Extract the source link and name from the first numbered headline in signals file.
    
    Returns:
        Tuple of (source_url, source_name) or None if not found.
        URL will have skip_landing=false instead of true.
    """
    try:
        content = signals_file.read_text()
    except Exception:
        return None
    
    top_stories_match = re.search(r'## 🔥 Top Stories(.+?)(?=##|$)', content, re.DOTALL)
    if not top_stories_match:
        return None
    
    top_stories_content = top_stories_match.group(1)
    
    # Pattern 1: <strong><a href="...">1. HEADLINE</a></strong> - <a href="SOURCE_URL">source</a>
    # Pattern 2: <strong>1. HEADLINE</strong> - <a href="SOURCE_URL">source</a>
    
    pattern1 = r'<strong[^>]*><a[^>]*>(\d+)\.\s*[^<]+</a></strong>\s*-\s*<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
    match = re.search(pattern1, top_stories_content)
    
    if not match:
        pattern2 = r'<strong[^>]*>(\d+)\.\s*[^<]+</strong>\s*-\s*<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
        match = re.search(pattern2, top_stories_content)
    
    if match and match.group(1) == "1":  # Make sure it's the first numbered headline
        source_url = match.group(2)
        source_name = match.group(3)
        
        # Change skip_landing=true to skip_landing=false
        source_url = source_url.replace("skip_landing=true", "skip_landing=false")
        
        return (source_url, source_name)
    return None


def parse_date_from_path(file_path: Path) -> Optional[datetime]:
    """Extract date from signals file path."""
    try:
        parts = file_path.parts
        if len(parts) >= 4:
            year = int(parts[-4])
            month = int(parts[-3])
            day = int(parts[-2])
            return datetime(year, month, day)
        # Fallback: try to extract from filename
        match = re.search(r'signals_(\d{4})-(\d{2})-(\d{2})\.md', file_path.name)
        if match:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except (ValueError, IndexError):
        pass
    return None


def format_date_entry(file_path: Path, date: datetime, writeup_dir: Path) -> str:
    """Format a date entry with headline."""
    project_root = Path.cwd()
    try:
        relative_path = file_path.relative_to(project_root)
    except ValueError:
        relative_path = file_path.relative_to(writeup_dir.parent)
    
    date_str = date.strftime('%B %d, %Y')
    day_name = date.strftime('%A')
    
    headline = extract_first_headline(file_path)
    source_info = extract_source_info(file_path)
    
    date_link = f"[**{day_name}, {date_str}**]({relative_path})"
    
    if headline:
        if source_info:
            source_url, source_name = source_info
            headline_text = f"{headline} [{source_name}]({source_url})"
        else:
            headline_text = headline
        return f"{date_link}\n{headline_text}"
    else:
        return date_link


def generate_monthly_readme(year: int, month: int, writeup_dir: Path) -> str:
    """Generate README content for a month."""
    month_dir = writeup_dir / str(year) / f"{month:02d}"
    
    if not month_dir.exists():
        return f"# {datetime(year, month, 1).strftime('%B %Y')} Archive\n\n*No signals found for this month.*\n"
    
    # Find all signals files in this month
    signals_files = list(month_dir.rglob("signals_*.md"))
    
    if not signals_files:
        return f"# {datetime(year, month, 1).strftime('%B %Y')} Archive\n\n*No signals found for this month.*\n"
    
    # Parse dates and sort
    files_with_dates = []
    for file_path in signals_files:
        date = parse_date_from_path(file_path)
        if date:
            files_with_dates.append((file_path, date))
    
    # Sort by date, most recent first
    files_with_dates.sort(key=lambda x: x[1], reverse=True)
    
    # Generate entries
    entries = []
    for file_path, date in files_with_dates:
        entries.append(format_date_entry(file_path, date, writeup_dir))
    
    entries_text = "\n\n".join(entries)
    
    month_name = datetime(year, month, 1).strftime('%B %Y')
    return f"# {month_name} Archive\n\n{entries_text}\n"


def main():
    parser = argparse.ArgumentParser(description="Generate monthly archive README files")
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Year (e.g., 2025)"
    )
    parser.add_argument(
        "--month",
        type=int,
        required=True,
        help="Month (1-12)"
    )
    parser.add_argument(
        "--writeup-dir",
        type=Path,
        default=Path("writeup"),
        help="Path to writeup directory (default: writeup)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output without writing file"
    )

    args = parser.parse_args()

    if not (1 <= args.month <= 12):
        print(f"Error: Month must be between 1 and 12, got {args.month}")
        return 1

    print(f"Generating archive for {datetime(args.year, args.month, 1).strftime('%B %Y')}...")
    
    readme_content = generate_monthly_readme(args.year, args.month, args.writeup_dir)
    
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - Would write:")
        print("=" * 60)
        print(readme_content)
        print("=" * 60)
        return 0
    
    # Write README to month directory
    month_dir = args.writeup_dir / str(args.year) / f"{args.month:02d}"
    month_dir.mkdir(parents=True, exist_ok=True)
    readme_path = month_dir / "README.md"
    
    readme_path.write_text(readme_content)
    print(f"✓ Created: {readme_path}")
    return 0


if __name__ == "__main__":
    exit(main())
