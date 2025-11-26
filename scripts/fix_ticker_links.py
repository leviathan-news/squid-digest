#!/usr/bin/env python3
"""Fix ticker links in all markdown files to use canonical_tag instead of id."""

import re
import json
from pathlib import Path
from typing import Dict

# Add parent directory to path to import modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from squid_digest.tools import LeviathanNewsFetcher


def get_canonical_tag_map() -> Dict[str, int]:
    """Fetch token data and build a mapping of symbol -> canonical_tag.
    
    Returns:
        Dictionary mapping symbol (uppercase) -> canonical_tag
    """
    print("Fetching token data from Leviathan API...")
    try:
        leviathan_fetcher = LeviathanNewsFetcher()
        token_data = leviathan_fetcher.fetch_tokens(save=False)
        
        canonical_map = {}
        for token in token_data.get('tokens', []):
            symbol = token.get('symbol', '').strip('$').upper()
            canonical_tag = token.get('canonical_tag')
            
            if symbol and canonical_tag:
                canonical_map[symbol] = canonical_tag
        
        print(f"✓ Found {len(canonical_map)} tokens with canonical tags")
        return canonical_map
    except Exception as e:
        print(f"Error fetching token data: {e}")
        return {}


def fix_links_in_file(file_path: Path, canonical_map: Dict[str, int]) -> bool:
    """Fix ticker links in a single markdown file.
    
    Args:
        file_path: Path to the markdown file
        canonical_map: Mapping of symbol -> canonical_tag
        
    Returns:
        True if any changes were made, False otherwise
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"  ⚠ Error reading {file_path}: {e}")
        return False
    
    original_content = content
    
    # Pattern to match: https://leviathannews.xyz/t/{id}/{symbol}?...
    # Also handles markdown links: [TEXT](https://leviathannews.xyz/t/{id}/{symbol}?...) and HTML links: <a href="...">
    pattern = r'https://leviathannews\.xyz/t/(\d+)/([A-Z0-9]+)(\?[^\)"\s]*)?'
    
    def replace_link(match):
        old_id = match.group(1)
        symbol = match.group(2).upper()
        query_params = match.group(3) or ''
        
        # Look up canonical_tag for this symbol
        canonical_tag = canonical_map.get(symbol)
        
        if canonical_tag:
            new_id = str(canonical_tag)
            if new_id != old_id:
                return f'https://leviathannews.xyz/t/{new_id}/{symbol}{query_params}'
        
        # If we don't have a mapping, return original
        return match.group(0)
    
    content = re.sub(pattern, replace_link, content)
    
    if content != original_content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"  ⚠ Error writing {file_path}: {e}")
            return False
    
    return False


def main():
    """Main function to fix all markdown files."""
    # Get canonical tag mapping
    canonical_map = get_canonical_tag_map()
    
    if not canonical_map:
        print("No canonical tags found. Exiting.")
        return
    
    # Find all markdown files in writeup folder
    writeup_dir = Path(__file__).parent.parent / "writeup"
    markdown_files = list(writeup_dir.rglob("*.md"))
    
    print(f"\nFound {len(markdown_files)} markdown files to check...")
    
    fixed_count = 0
    for md_file in markdown_files:
        if fix_links_in_file(md_file, canonical_map):
            print(f"  ✓ Fixed: {md_file.relative_to(writeup_dir.parent)}")
            fixed_count += 1
    
    print(f"\n✓ Fixed links in {fixed_count} files")


if __name__ == "__main__":
    main()
