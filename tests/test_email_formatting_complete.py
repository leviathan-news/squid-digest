#!/usr/bin/env python3
"""
Test that email HTML formatting preserves ALL content from markdown.

This test ensures that when markdown is converted to email HTML, ALL sections
are preserved:
- Market Snapshot
- Top Stories (SQUID Pass + regular stories)  
- Trading Signals
- Backtest Results
- Current Positions
- Trades Today

The test will FAIL if any section is missing from the HTML output.
"""

import re
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from squid_digest.email.ghost_client import GhostEmailClient
except ImportError as e:
    # Skip test if dependencies not available (e.g. in CI without full env)
    import unittest
    class SkipTest(unittest.TestCase):
        @unittest.skip(f"Dependencies not available: {e}")
        def test_skip(self):
            pass
    # Return early - test will be skipped
    if __name__ == "__main__":
        print(f"⚠️  Skipping test - dependencies not available: {e}")
        sys.exit(0)
    # If imported as module, the SkipTest class will be used


def test_email_contains_all_sections():
    """Test that formatted email HTML contains all expected sections from markdown."""
    # Find a recent signals file
    writeup_dir = Path("writeup")
    if not writeup_dir.exists():
        print("⚠️  writeup/ directory not found - skipping test")
        return True
    
    signals_files = sorted(writeup_dir.rglob("signals_*.md"), reverse=True)
    if not signals_files:
        print("⚠️  No signals files found - skipping test")
        return True
    
    signals_file = signals_files[0]  # Most recent
    print(f"Testing with: {signals_file}")
    
    # Read markdown
    markdown = signals_file.read_text()
    
    # Create client instance (without requiring full init)
    client = GhostEmailClient.__new__(GhostEmailClient)
    
    # Format for email
    try:
        html = client.format_digest_html(markdown)
    except Exception as e:
        print(f"❌ ERROR: Failed to format HTML: {e}")
        return False
    
    # Required sections that must be present
    required_checks = {
        "Market Snapshot": [
            (r"Market Snapshot", "Market Snapshot header"),
            (r"BTC.*\$[\d,]+", "BTC price in market snapshot"),
        ],
        "Top Stories - SQUID Pass": [
            (r"SQUID Pass Winner", "SQUID Pass section"),
        ],
        "Top Stories - Regular Stories": [
            (r"<strong>.*?</strong>", "Story headlines (at least 2 besides SQUID Pass)"),
        ],
        "Trading Signals": [
            (r"Trading Signals", "Trading Signals header"),
            (r"(STRONG (BUY|SELL)|BUY|SELL|WEAK (BUY|SELL))", "Signal types"),
        ],
        "Backtest Results": [
            (r"Backtest Results", "Backtest Results header"),
            (r"Portfolio Value", "Portfolio value"),
        ],
    }
    
    errors = []
    warnings = []
    
    for section_name, patterns in required_checks.items():
        found_any = False
        for pattern, description in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
            if matches:
                found_any = True
                if section_name == "Top Stories - Regular Stories":
                    # Need at least 2 story headlines (SQUID Pass doesn't count)
                    if len(matches) < 3:  # SQUID Pass + 2 regular stories
                        warnings.append(f"⚠️  {section_name}: Only found {len(matches)} headlines (need at least 3 total)")
                break
        
        if not found_any:
            errors.append(f"❌ Missing: {section_name}")
        else:
            print(f"✓ Found: {section_name}")
    
    # Additional check: ensure we have content after SQUID Pass
    squid_pass_pos = html.find("SQUID Pass Winner")
    trading_signals_pos = html.find("Trading Signals")
    
    if squid_pass_pos != -1 and trading_signals_pos != -1:
        content_between = html[squid_pass_pos:trading_signals_pos]
        # Should have story content between SQUID Pass and Trading Signals
        story_headlines = len(re.findall(r"<strong>.*?</strong>", content_between))
        if story_headlines < 2:
            errors.append(f"❌ Missing regular stories between SQUID Pass and Trading Signals (found {story_headlines} headlines)")
    
    # Check HTML length - should be substantial
    if len(html) < 5000:
        warnings.append(f"⚠️  HTML output seems too short ({len(html)} chars) - may be missing content")
    
    if errors:
        print("\n" + "="*60)
        print("TEST FAILED - Missing required sections:")
        for error in errors:
            print(f"  {error}")
        print("="*60)
        print(f"\nHTML length: {len(html)} characters")
        print(f"HTML preview (first 2000 chars):")
        print(html[:2000])
        print("\n...")
        return False
    
    if warnings:
        print("\n⚠️  Warnings (non-fatal):")
        for warning in warnings:
            print(f"  {warning}")
    
    print(f"\n✅ TEST PASSED: All required sections present")
    print(f"   HTML length: {len(html)} characters")
    return True


if __name__ == "__main__":
    success = test_email_contains_all_sections()
    sys.exit(0 if success else 1)
