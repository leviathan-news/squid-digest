#!/usr/bin/env python3
"""
Update writeup/README.md with recent headlines and navigation.

This script:
1. Extracts top 5 headlines from the latest signals file
2. Finds all signals files from the trailing 4 weeks
3. Organizes them by week with bias towards most recent
4. Updates the README between markers

Usage:
    python scripts/update_writeup_readme.py [--readme PATH] [--writeup-dir PATH]
"""

import argparse
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Tuple


def find_latest_signals_file(writeup_dir: Path) -> Optional[Path]:
    """Find the most recent signals_*.md file in the writeup directory."""
    writeup_dir = writeup_dir.resolve()
    signals_files = list(writeup_dir.rglob("signals_*.md"))
    if not signals_files:
        return None
    signals_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return signals_files[0]


def extract_headlines(signals_file: Path, limit: int = 5) -> List[str]:
    """Extract top headlines from signals markdown file."""
    content = signals_file.read_text()
    headlines = []

    top_stories_match = re.search(r'## 🔥 Top Stories(.+?)(?=##|$)', content, re.DOTALL)
    if not top_stories_match:
        return headlines

    top_stories_content = top_stories_match.group(1)
    
    # Pattern 1: <strong><a href="...">N. HEADLINE</a></strong> (headline inside link)
    # Pattern 2: <strong>N. HEADLINE</strong> (headline directly in strong tag)
    # Try pattern 1 first (more common in newer files)
    pattern1 = r'<strong[^>]*><a[^>]*>(\d+)\.\s*([^<]+)</a></strong>'
    pattern2 = r'<strong[^>]*>(\d+)\.\s*([^<]+)</strong>'
    
    matches = re.findall(pattern1, top_stories_content)
    if not matches:
        matches = re.findall(pattern2, top_stories_content)

    for num, headline in matches[:limit]:
        headline = headline.strip()
        headlines.append(headline)

    return headlines


def extract_headlines_with_sources(signals_file: Path, limit: int = 5) -> List[Tuple[str, Optional[Tuple[str, str]]]]:
    """Extract top headlines with their source info from signals markdown file.
    
    Returns:
        List of tuples: (headline, (source_url, source_name) or None)
    """
    content = signals_file.read_text()
    results = []

    top_stories_match = re.search(r'## 🔥 Top Stories(.+?)(?=##|$)', content, re.DOTALL)
    if not top_stories_match:
        return results

    top_stories_content = top_stories_match.group(1)
    
    # Pattern 1: <strong><a href="...">N. HEADLINE</a></strong> - <a href="SOURCE_URL">source</a>
    # Pattern 2: <strong>N. HEADLINE</strong> - <a href="SOURCE_URL">source</a>
    pattern1 = r'<strong[^>]*><a[^>]*>(\d+)\.\s*([^<]+)</a></strong>\s*-\s*<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
    pattern2 = r'<strong[^>]*>(\d+)\.\s*([^<]+)</strong>\s*-\s*<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
    
    matches = re.findall(pattern1, top_stories_content)
    if not matches:
        matches = re.findall(pattern2, top_stories_content)

    for match in matches[:limit]:
        num = match[0]
        headline = match[1].strip()
        source_url = match[2]
        source_name = match[3]
        
        # Change skip_landing=true to skip_landing=false
        source_url = source_url.replace("skip_landing=true", "skip_landing=false")
        
        results.append((headline, (source_url, source_name)))
    
    # If we didn't find any matches with sources, try to get headlines without sources as fallback
    if not results:
        plain_headlines = extract_headlines(signals_file, limit=limit)
        results = [(h, None) for h in plain_headlines]

    return results


def extract_first_headline(signals_file: Path) -> Optional[str]:
    """Extract the first (top) headline from a signals file."""
    headlines = extract_headlines(signals_file, limit=1)
    return headlines[0] if headlines else None


def parse_date_from_path(file_path: Path) -> Optional[datetime]:
    """Extract date from signals file path (YYYY/MM/DD/signals_YYYY-MM-DD.md)."""
    try:
        # Try to extract from path structure: writeup/YYYY/MM/DD/signals_YYYY-MM-DD.md
        # Path parts: [..., 'YYYY', 'MM', 'DD', 'signals_YYYY-MM-DD.md']
        parts = file_path.parts
        if len(parts) >= 4:
            # parts[-4] = year, parts[-3] = month, parts[-2] = day, parts[-1] = filename
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


def find_signals_files_in_range(writeup_dir: Path, days_back: int = 28) -> List[Tuple[Path, datetime]]:
    """Find all signals files from the last N days, sorted by date."""
    writeup_dir = writeup_dir.resolve()
    signals_files = list(writeup_dir.rglob("signals_*.md"))
    
    cutoff_date = datetime.now() - timedelta(days=days_back)
    results = []
    
    for file_path in signals_files:
        date = parse_date_from_path(file_path)
        if date and date >= cutoff_date:
            results.append((file_path, date))
    
    # Sort by date, most recent first
    results.sort(key=lambda x: x[1], reverse=True)
    return results


# Removed unused function


def extract_source_info(signals_file: Path) -> Optional[Tuple[str, str]]:
    """Extract the source link and name from the first numbered headline in signals file.
    
    Returns:
        Tuple of (source_url, source_name) or None if not found.
        URL will have skip_landing=false instead of true.
    """
    content = signals_file.read_text()
    top_stories_match = re.search(r'## 🔥 Top Stories(.+?)(?=##|$)', content, re.DOTALL)
    if not top_stories_match:
        return None
    
    top_stories_content = top_stories_match.group(1)
    
    # Pattern 1: <strong><a href="...">1. HEADLINE</a></strong> - <a href="SOURCE_URL">source</a>
    # Pattern 2: <strong>1. HEADLINE</strong> - <a href="SOURCE_URL">source</a>
    
    # Try pattern 1 first (headline inside link)
    pattern1 = r'<strong[^>]*><a[^>]*>(\d+)\.\s*[^<]+</a></strong>\s*-\s*<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
    match = re.search(pattern1, top_stories_content)
    
    if not match:
        # Try pattern 2 (headline directly in strong)
        pattern2 = r'<strong[^>]*>(\d+)\.\s*[^<]+</strong>\s*-\s*<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>'
        match = re.search(pattern2, top_stories_content)
    
    if match and match.group(1) == "1":  # Make sure it's the first numbered headline
        source_url = match.group(2)
        source_name = match.group(3)
        
        # Change skip_landing=true to skip_landing=false
        source_url = source_url.replace("skip_landing=true", "skip_landing=false")
        
        return (source_url, source_name)
    return None


def extract_source_link(signals_file: Path) -> Optional[str]:
    """Extract the source link from the first numbered headline in signals file.
    
    Deprecated: Use extract_source_info() instead to get both URL and name.
    """
    result = extract_source_info(signals_file)
    return result[0] if result else None


def format_date_link(file_path: Path, date: datetime, writeup_dir: Path, headline: Optional[str] = None) -> str:
    """Format a date link for navigation with headline hook."""
    # Calculate relative path from project root
    project_root = Path.cwd()
    try:
        relative_path = file_path.relative_to(project_root)
    except ValueError:
        # Fallback: use path relative to writeup dir
        relative_path = file_path.relative_to(writeup_dir.parent)
    date_str = date.strftime('%B %d, %Y')
    day_name = date.strftime('%A')
    
    # Extract source info (URL and formatted name)
    source_info = extract_source_info(file_path)
    
    # Format: [**DATE**](link) on one line, headline on next
    date_link = f"[**{day_name}, {date_str}**]({relative_path})"
    
    if headline:
        # Show full headline without truncation
        if source_info:
            source_url, source_name = source_info
            headline_text = f"{headline} [{source_name}]({source_url})"
        else:
            headline_text = headline
        return f"{date_link}\n{headline_text}"
    else:
        return date_link


def format_recent_section(
    latest_file: Path,
    latest_date: datetime,
    headlines: List[str],
    writeup_dir: Path
) -> str:
    """Format the most recent headlines section."""
    date_str = latest_date.strftime('%B %d, %Y')
    # Calculate relative path from project root
    project_root = Path.cwd()
    try:
        relative_path = latest_file.relative_to(project_root)
    except ValueError:
        # Fallback: use path relative to writeup dir
        relative_path = latest_file.relative_to(writeup_dir.parent)
    
    # Extract headlines with source info
    headlines_with_sources = extract_headlines_with_sources(latest_file, limit=5)
    
    # Format headlines with source links
    headline_bullets = []
    for headline_text, source_info in headlines_with_sources:
        if source_info:
            source_url, source_name = source_info
            headline_bullets.append(f"- **{headline_text}** [{source_name}]({source_url})")
        else:
            headline_bullets.append(f"- **{headline_text}**")
    
    # Fallback: if we couldn't extract with sources, use the plain headlines
    if not headline_bullets:
        headline_bullets = [f"- **{h}**" for h in headlines]
    
    headline_bullets_text = "\n".join(headline_bullets)
    
    # Get GitHub repo URL (try to detect from git remote or use default)
    github_url = "https://github.com/your-org/squid-digest"  # Default, should be updated
    try:
        import subprocess
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            remote_url = result.stdout.strip()
            # Convert git@github.com:user/repo.git to https://github.com/user/repo
            if remote_url.startswith("git@"):
                remote_url = remote_url.replace("git@github.com:", "https://github.com/").replace(".git", "")
            elif remote_url.startswith("https://"):
                remote_url = remote_url.replace(".git", "")
            github_url = remote_url
    except Exception:
        pass  # Use default
    
    github_readme_url = f"{github_url}/blob/main/{relative_path}"
    
    return f"""## 🔥 Latest Headlines ({date_str})

{headline_bullets_text}

📊 [View Full Analysis →]({relative_path}) | 🌐 [Read on Web](https://digest.leviathannews.xyz) | 📝 [Read on GitHub]({github_readme_url})

---

"""


def format_week_navigation(
    files_with_dates: List[Tuple[Path, datetime]],
    writeup_dir: Path,
    week_num: int
) -> str:
    """Format navigation for a week's worth of files with headlines."""
    if not files_with_dates:
        return ""
    
    # Get date range for the week
    dates = [d for _, d in files_with_dates]
    week_start = min(dates)
    week_end = max(dates)
    
    # Extract headlines for all files
    links = []
    for file_path, date in files_with_dates:
        headline = extract_first_headline(file_path)
        link_text = format_date_link(file_path, date, writeup_dir, headline)
        links.append(link_text)
    
    links_text = "\n\n".join(links)  # Double newline between entries
    
    # Format header based on week number
    if week_num == 1:
        header = f"### 📅 This Week ({week_start.strftime('%b %d')} - {week_end.strftime('%b %d')})"
    elif week_num == 2:
        header = f"### 📅 Last Week ({week_start.strftime('%b %d')} - {week_end.strftime('%b %d')})"
    else:
        header = f"### 📅 Week of {week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}"
    
    return f"{header}\n\n{links_text}\n"


def format_navigation_section(
    files_with_dates: List[Tuple[Path, datetime]],
    writeup_dir: Path
) -> str:
    """Format the navigation section with trailing 4 weeks, biased towards recent."""
    if not files_with_dates:
        return "### 📅 Recent Publications\n\n*No recent signals found.*\n"
    
    # Split into weeks
    today = datetime.now()
    week1_files = []  # Last 7 days
    week2_files = []  # Days 8-14
    week3_files = []  # Days 15-21
    week4_files = []  # Days 22-28
    
    for file_path, date in files_with_dates:
        days_ago = (today - date).days
        if days_ago <= 7:
            week1_files.append((file_path, date))
        elif days_ago <= 14:
            week2_files.append((file_path, date))
        elif days_ago <= 21:
            week3_files.append((file_path, date))
        elif days_ago <= 28:
            week4_files.append((file_path, date))
    
    sections = []
    
    if week1_files:
        sections.append(format_week_navigation(week1_files, writeup_dir, week_num=1))
    if week2_files:
        sections.append(format_week_navigation(week2_files, writeup_dir, week_num=2))
    if week3_files:
        sections.append(format_week_navigation(week3_files, writeup_dir, week_num=3))
    if week4_files:
        sections.append(format_week_navigation(week4_files, writeup_dir, week_num=4))
    
    return "## 📚 Recent Publications (Last 4 Weeks)\n\n" + "\n".join(sections)


def update_writeup_readme(readme_path: Path, new_section: str) -> bool:
    """Update writeup README.md with new content between markers."""
    if not readme_path.exists():
        print(f"Error: README not found at {readme_path}")
        return False

    content = readme_path.read_text()
    start_marker = "<!-- DAILY_UPDATE_START -->"
    end_marker = "<!-- DAILY_UPDATE_END -->"

    if start_marker not in content or end_marker not in content:
        print(f"Error: Markers not found in README")
        print(f"Please add {start_marker} and {end_marker} to writeup/README.md")
        return False

    pattern = f"({re.escape(start_marker)}).*?({re.escape(end_marker)})"
    replacement = f"{start_marker}\n{new_section}{end_marker}"

    updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    readme_path.write_text(updated_content)
    print(f"✓ README updated successfully")
    return True


def main():
    parser = argparse.ArgumentParser(description="Update writeup README with recent headlines and navigation")
    parser.add_argument(
        "--readme",
        type=Path,
        default=Path("writeup/README.md"),
        help="Path to writeup README.md (default: writeup/README.md)"
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
        help="Print output without updating README"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("📰 Updating Writeup README with Recent Headlines")
    print("=" * 60)
    print()

    # Find latest signals file
    print(f"Searching for latest signals file in {args.writeup_dir}...")
    latest_file = find_latest_signals_file(args.writeup_dir)

    if not latest_file:
        print("✗ Error: No signals file found")
        return 1

    latest_date = parse_date_from_path(latest_file)
    if not latest_date:
        print("✗ Error: Could not parse date from signals file")
        return 1

    print(f"✓ Found latest: {latest_file.relative_to(Path.cwd())} ({latest_date.strftime('%Y-%m-%d')})")

    # Extract headlines
    print("\nExtracting headlines...")
    headlines = extract_headlines(latest_file, limit=5)

    if not headlines:
        print("⚠ Warning: Could not extract headlines")
        headlines = ["*No headlines found*"]

    print(f"✓ Extracted {len(headlines)} headlines")

    # Find files from last 4 weeks
    print("\nFinding signals files from last 4 weeks...")
    files_with_dates = find_signals_files_in_range(args.writeup_dir, days_back=28)
    print(f"✓ Found {len(files_with_dates)} signals files")

    # Format sections
    print("\nFormatting sections...")
    recent_section = format_recent_section(latest_file, latest_date, headlines, args.writeup_dir)
    navigation_section = format_navigation_section(files_with_dates, args.writeup_dir)

    new_section = recent_section + "\n" + navigation_section

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - Would update README with:")
        print("=" * 60)
        print(new_section)
        print("=" * 60)
        return 0

    # Update README
    print(f"\nUpdating {args.readme}...")
    success = update_writeup_readme(args.readme, new_section)

    if success:
        print("\n✓ Writeup README updated successfully!")
        return 0
    else:
        print("\n✗ Failed to update README")
        return 1


if __name__ == "__main__":
    exit(main())
