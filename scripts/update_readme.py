#!/usr/bin/env python3
"""
Update README.md with today's trading signals and portfolio performance.

This script:
1. Extracts top 5 headlines with URLs and sources from the latest signals file
2. Gets portfolio performance from both portfolio_state_buy.json and portfolio_state_sell.json
3. Updates the "above the fold" section in README.md between markers

Usage:
    python scripts/update_readme.py [--readme PATH] [--writeup-dir PATH] [--dry-run]
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional


def find_latest_signals_file(writeup_dir: Path) -> Optional[Path]:
    """Find the most recent signals_*.md file in the writeup directory."""
    # Make absolute to ensure consistent path handling
    writeup_dir = writeup_dir.resolve()

    # Search in YMD structure
    signals_files = list(writeup_dir.rglob("signals_*.md"))
    if not signals_files:
        return None

    # Sort by modification time, most recent first
    # Use st_mtime (modification time) for better reliability
    try:
        signals_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError as e:
        # If stat fails, try sorting by filename (which contains date)
        print(f"  Warning: Could not stat files, sorting by filename: {e}")
        signals_files.sort(key=lambda p: p.name, reverse=True)
    
    latest_file = signals_files[0]
    
    # Validate the file is readable and not empty
    try:
        if latest_file.stat().st_size == 0:
            print(f"  Warning: Latest signals file is empty: {latest_file}")
            # Try the next file if available
            if len(signals_files) > 1:
                print(f"  Falling back to: {signals_files[1]}")
                return signals_files[1]
    except OSError:
        pass  # If we can't stat, continue anyway
    
    return latest_file


def extract_headlines(signals_file: Path, limit: int = 5) -> List[Tuple[str, str, str]]:
    """
    Extract top headlines from signals markdown file with URLs and sources.

    Args:
        signals_file: Path to signals_*.md file
        limit: Number of headlines to extract (default 5)

    Returns:
        List of tuples: [(headline, url, source), ...]
    """
    # Validate file exists and has content
    if not signals_file.exists():
        print(f"Error: Signals file does not exist: {signals_file}")
        return []
    
    try:
        content = signals_file.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error: Could not read signals file: {e}")
        return []
    
    if not content or len(content.strip()) == 0:
        print(f"Warning: Signals file is empty: {signals_file}")
        return []

    headlines = []

    # Find the Top Stories section
    top_stories_match = re.search(r'## 🔥 Top Stories(.+?)(?=##|$)', content, re.DOTALL)
    if not top_stories_match:
        print("Warning: Could not find '## 🔥 Top Stories' section in file")
        print(f"  File size: {len(content)} bytes")
        print(f"  First 500 chars: {content[:500]}")
        # Try to find any section that might contain stories
        if "Top Stories" in content or "top stories" in content.lower():
            print("  Note: Found 'Top Stories' text but not in expected format")
        return headlines

    top_stories_content = top_stories_match.group(1)
    
    # Debug: Show a snippet of the content we're searching
    print(f"  Found Top Stories section ({len(top_stories_content)} chars)")

    # Extract headlines with URLs and sources from table rows
    # Support multiple formats:
    # Format 1 (old): <strong>N. HEADLINE</strong> - <a href="URL">SOURCE</a>
    # Format 2 (new): N. HEADLINE - <a href="URL"><strong>SOURCE</strong></a>
    patterns = [
        # Old format: <strong>N. HEADLINE</strong> - <a href="URL">SOURCE</a>
        (r'<strong[^>]*>(\d+)\.\s*([^<]+)</strong>\s*-\s*<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', 'old'),
        # New format: N. HEADLINE - <a href="URL"><strong>SOURCE</strong></a>
        # Match headline up to the dash and link, stopping before < tag (but allow - in headline)
        (r'(\d+)\.\s*([^<]+?)\s*-\s*<a[^>]*href="([^"]+)"[^>]*><strong[^>]*>([^<]+)</strong></a>', 'new'),
    ]
    
    matches = []
    used_pattern = None
    
    for pattern, pattern_name in patterns:
        pattern_matches = re.findall(pattern, top_stories_content)
        if pattern_matches:
            matches = pattern_matches
            used_pattern = pattern_name
            print(f"  Found {len(matches)} headline matches using {pattern_name} format")
            break
    
    if not matches:
        print("Warning: No numbered headlines found matching expected patterns")
        print("  Tried patterns:")
        print("    1. <strong>N. HEADLINE</strong> - <a href=\"URL\">SOURCE</a>")
        print("    2. N. HEADLINE - <a href=\"URL\"><strong>SOURCE</strong></a>")
        print(f"  Content preview (first 1000 chars): {top_stories_content[:1000]}")
        return headlines

    for match in matches[:limit]:
        if len(match) == 4:
            num, headline, url, source = match
            # Clean up the headline
            headline = headline.strip()
            source = source.strip()
            if headline and url and source:
                headlines.append((headline, url, source))
            else:
                print(f"  Warning: Skipping incomplete headline match: num={num}, headline={headline[:50]}...")
        else:
            print(f"  Warning: Unexpected match format (expected 4 groups, got {len(match)}): {match}")

    return headlines


def get_portfolio_snapshot(portfolio_file: Path) -> Tuple[float, float, str]:
    """
    Get portfolio performance snapshot from state file.

    Args:
        portfolio_file: Path to portfolio_state_buy.json or portfolio_state_sell.json

    Returns:
        Tuple of (portfolio_value, total_return_pct, date)
    """
    if not portfolio_file.exists():
        print(f"  Warning: Portfolio file not found: {portfolio_file}")
        print(f"  Using default values (0.0, 0.0, today's date)")
        return (0.0, 0.0, datetime.now().strftime('%Y-%m-%d'))

    try:
        with open(portfolio_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  Error: Invalid JSON in portfolio file: {portfolio_file}")
        print(f"  JSON error: {e}")
        print(f"  Using default values")
        return (0.0, 0.0, datetime.now().strftime('%Y-%m-%d'))
    except Exception as e:
        print(f"  Error: Could not read portfolio file: {portfolio_file}")
        print(f"  Error: {e}")
        print(f"  Using default values")
        return (0.0, 0.0, datetime.now().strftime('%Y-%m-%d'))

    # Calculate portfolio value
    cash = state.get('cash', 0)
    positions = state.get('positions', {})

    # Get latest daily value if available
    daily_values = state.get('daily_values', [])
    if daily_values:
        try:
            latest = daily_values[-1]
            # daily_values format: [timestamp, value] or {"date": ..., "total_value": ...}
            if isinstance(latest, list) and len(latest) >= 2:
                date_str = latest[0].split('T')[0]  # Extract date from ISO timestamp
                portfolio_value = float(latest[1])
            elif isinstance(latest, dict):
                portfolio_value = float(latest.get('total_value', cash))
                date_str = latest.get('date', datetime.now().strftime('%Y-%m-%d'))
            else:
                print(f"  Warning: Unexpected daily_values format, using cash value")
                portfolio_value = float(cash)
                date_str = datetime.now().strftime('%Y-%m-%d')
        except (ValueError, TypeError, IndexError) as e:
            print(f"  Warning: Error parsing daily_values: {e}")
            print(f"  Using cash value instead")
            portfolio_value = float(cash)
            date_str = datetime.now().strftime('%Y-%m-%d')
    else:
        portfolio_value = float(cash)
        date_str = datetime.now().strftime('%Y-%m-%d')

    # Calculate return percentage
    try:
        initial_capital = float(state.get('initial_capital', 10000))
        if initial_capital > 0:
            total_return_pct = ((portfolio_value - initial_capital) / initial_capital) * 100
        else:
            print(f"  Warning: initial_capital is 0 or invalid, return % will be 0")
            total_return_pct = 0.0
    except (ValueError, TypeError) as e:
        print(f"  Warning: Error calculating return percentage: {e}")
        total_return_pct = 0.0

    return (portfolio_value, total_return_pct, date_str)


def format_above_fold_section(
    headlines: List[Tuple[str, str, str]],
    buy_portfolio_value: float,
    buy_total_return_pct: float,
    sell_portfolio_value: float,
    sell_total_return_pct: float,
    signals_file: Path,
    date: str
) -> str:
    """
    Format the above-the-fold section for README.

    Args:
        headlines: List of tuples (headline, url, source)
        buy_portfolio_value: Buy strategy portfolio value in USD
        buy_total_return_pct: Buy strategy total return percentage
        sell_portfolio_value: Sell strategy portfolio value in USD
        sell_total_return_pct: Sell strategy total return percentage
        signals_file: Path to the signals file (for link)
        date: Date string

    Returns:
        Formatted markdown string
    """
    # Format date with error handling
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        date_formatted = date_obj.strftime('%B %d, %Y')
        date_mmddyy = date_obj.strftime('%m-%d-%y')
    except ValueError:
        # If date parsing fails, try to extract from filename or use today
        print(f"  Warning: Could not parse date '{date}', trying to extract from filename")
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', signals_file.name)
        if date_match:
            date = date_match.group(1)
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                date_formatted = date_obj.strftime('%B %d, %Y')
                date_mmddyy = date_obj.strftime('%m-%d-%y')
            except ValueError:
                date_formatted = date
                date_mmddyy = date[-5:] if len(date) >= 5 else date
        else:
            date_formatted = datetime.now().strftime('%B %d, %Y')
            date_mmddyy = datetime.now().strftime('%m-%d-%y')

    # Format headlines as bullets with links
    if headlines:
        headline_bullets = "\n".join([
            f"- **{headline}** [{source}]({url})"
            for headline, url, source in headlines
        ])
    else:
        headline_bullets = "*No headlines available*"

    # Format return signs
    buy_return_sign = "+" if buy_total_return_pct >= 0 else ""
    sell_return_sign = "+" if sell_total_return_pct >= 0 else ""

    # Get relative path for signals file link
    relative_path = signals_file.relative_to(Path.cwd())

    section = f"""## 📊 Latest News Headlines ({date_formatted})

### 🔥 Top Headlines
{headline_bullets}

### 📈 Portfolio Performance
**Buy Strategy:** ${buy_portfolio_value:,.2f} ({buy_return_sign}{buy_total_return_pct:.2f}%) | [Full Analysis →]({relative_path})
**Sell Strategy:** ${sell_portfolio_value:,.2f} ({sell_return_sign}{sell_total_return_pct:.2f}%) | [Full Analysis →]({relative_path})

**GitHub:** {date_mmddyy} | [Archives](writeup/)
**digest.leviathannews.xyz:** {date_mmddyy} | [Archives](https://digest.leviathannews.xyz)

---
"""
    return section


def update_readme(readme_path: Path, new_section: str) -> bool:
    """
    Update README.md with new above-the-fold section between markers.

    Args:
        readme_path: Path to README.md
        new_section: New section content to insert

    Returns:
        True if successful, False otherwise
    """
    if not readme_path.exists():
        print(f"Error: README not found at {readme_path}")
        return False

    try:
        content = readme_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error: Could not read README file: {e}")
        return False

    # Define markers
    start_marker = "<!-- DAILY_UPDATE_START -->"
    end_marker = "<!-- DAILY_UPDATE_END -->"

    # Check if markers exist
    if start_marker not in content:
        print(f"Error: Start marker not found in README")
        print(f"Please add {start_marker} to README.md")
        return False
    
    if end_marker not in content:
        print(f"Error: End marker not found in README")
        print(f"Please add {end_marker} to README.md")
        return False

    # Replace content between markers
    pattern = f"({re.escape(start_marker)}).*?({re.escape(end_marker)})"
    replacement = f"{start_marker}\n{new_section}{end_marker}"

    updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Verify the replacement actually happened
    if updated_content == content:
        print(f"Warning: Content replacement did not change the file")
        print(f"  This might indicate the markers are malformed or the pattern didn't match")
        return False

    # Write back
    try:
        readme_path.write_text(updated_content, encoding='utf-8')
        print(f"✓ README updated successfully")
        print(f"  Headlines: {len(new_section.splitlines())} lines")
        return True
    except Exception as e:
        print(f"Error: Could not write README file: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Update README with daily trading signals")
    parser.add_argument(
        "--readme",
        type=Path,
        default=Path("README.md"),
        help="Path to README.md (default: README.md)"
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
    parser.add_argument(
        "--allow-empty-headlines",
        action="store_true",
        help="Continue even if no headlines can be extracted (use empty list)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("📊 Updating README with Daily Trading Signals")
    print("=" * 60)
    print()

    # Find latest signals file
    print(f"Searching for latest signals file in {args.writeup_dir}...")
    signals_file = find_latest_signals_file(args.writeup_dir)

    if not signals_file:
        print("✗ Error: No signals file found")
        return 1

    print(f"✓ Found: {signals_file.relative_to(Path.cwd())}")
    
    # Validate file exists and has content
    if not signals_file.exists():
        print(f"✗ Error: Signals file does not exist: {signals_file}")
        return 1
    
    file_size = signals_file.stat().st_size
    print(f"  File size: {file_size} bytes")
    
    if file_size == 0:
        print("✗ Error: Signals file is empty")
        return 1

    # Extract headlines
    print("\nExtracting headlines...")
    headlines = extract_headlines(signals_file, limit=5)

    if not headlines:
        if args.allow_empty_headlines:
            print("⚠ Warning: Could not extract headlines, but continuing with empty list")
            print("  This may result in an incomplete README update")
        else:
            print("✗ Error: Could not extract headlines")
            print("\nDiagnostic information:")
            print(f"  File: {signals_file}")
            print(f"  File exists: {signals_file.exists()}")
            print(f"  File size: {file_size} bytes")
            try:
                content_preview = signals_file.read_text(encoding='utf-8')[:500]
                print(f"  Content preview (first 500 chars):\n{content_preview}")
            except Exception as e:
                print(f"  Could not read file: {e}")
            return 1

    print(f"✓ Extracted {len(headlines)} headlines")
    for i, (headline, url, source) in enumerate(headlines, 1):
        print(f"  {i}. {headline[:60]}... [{source}]({url[:50]}...)")

    # Get portfolio snapshots for both strategies
    writeup_dir = args.writeup_dir.resolve()
    buy_portfolio_file = writeup_dir / "portfolio_state_buy.json"
    sell_portfolio_file = writeup_dir / "portfolio_state_sell.json"

    print(f"\nReading buy strategy portfolio state from {buy_portfolio_file}...")
    buy_portfolio_value, buy_total_return_pct, date = get_portfolio_snapshot(buy_portfolio_file)
    if buy_portfolio_value == 0.0 and not buy_portfolio_file.exists():
        print(f"  ⚠ Warning: Buy portfolio file missing, using default values")
    print(f"✓ Buy Strategy: ${buy_portfolio_value:,.2f} ({buy_total_return_pct:+.2f}%)")

    print(f"\nReading sell strategy portfolio state from {sell_portfolio_file}...")
    sell_portfolio_value, sell_total_return_pct, _ = get_portfolio_snapshot(sell_portfolio_file)
    if sell_portfolio_value == 0.0 and not sell_portfolio_file.exists():
        print(f"  ⚠ Warning: Sell portfolio file missing, using default values")
    print(f"✓ Sell Strategy: ${sell_portfolio_value:,.2f} ({sell_total_return_pct:+.2f}%)")
    
    # Validate date was extracted
    if not date or date == datetime.now().strftime('%Y-%m-%d'):
        # Try to extract date from signals file name as fallback
        signals_date_match = re.search(r'(\d{4}-\d{2}-\d{2})', signals_file.name)
        if signals_date_match:
            date = signals_date_match.group(1)
            print(f"  Using date from signals filename: {date}")

    # Format above-the-fold section
    print("\nFormatting above-the-fold section...")
    new_section = format_above_fold_section(
        headlines=headlines,
        buy_portfolio_value=buy_portfolio_value,
        buy_total_return_pct=buy_total_return_pct,
        sell_portfolio_value=sell_portfolio_value,
        sell_total_return_pct=sell_total_return_pct,
        signals_file=signals_file,
        date=date
    )

    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - Would update README with:")
        print("=" * 60)
        print(new_section)
        print("=" * 60)
        return 0

    # Update README
    print(f"\nUpdating {args.readme}...")
    success = update_readme(args.readme, new_section)

    if success:
        print("\n✓ README updated successfully!")
        return 0
    else:
        print("\n✗ Failed to update README")
        return 1


if __name__ == "__main__":
    exit(main())
