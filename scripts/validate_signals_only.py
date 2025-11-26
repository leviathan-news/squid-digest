#!/usr/bin/env python3
"""
Validate that only signals format is used - digest format is DEPRECATED.

This script ensures:
1. ACTIVE_PROMPT defaults to 'signals', not 'digest'
2. No code can accidentally generate digest format
3. Generated files are signals format, not digest
"""

import os
import sys
from pathlib import Path

def check_template_defaults():
    """Check that template.py defaults to 'signals', not 'digest'."""
    template_path = Path("src/squid_digest/context/prompts/template.py")
    
    if not template_path.exists():
        print(f"❌ ERROR: {template_path} not found")
        return False
    
    content = template_path.read_text()
    
    # Check that default is 'signals', not 'digest'
    if "os.getenv('ACTIVE_PROMPT', 'digest')" in content:
        print("❌ ERROR: template.py still defaults to 'digest' - must default to 'signals'")
        return False
    
    if "os.getenv('ACTIVE_PROMPT', 'signals')" not in content:
        print("❌ ERROR: template.py must default to 'signals'")
        return False
    
    # Check that digest is deprecated/enforced
    if "DEPRECATED" not in content.upper() or "digest" not in content.lower():
        print("⚠️  WARNING: template.py should explicitly deprecate digest format")
        # Not a hard failure, but good to have
    
    print("✓ template.py defaults to 'signals'")
    return True

def check_no_digest_generation():
    """Check that workflow and scripts only generate signals, not digest."""
    workflow_path = Path(".github/workflows/draft-digest.yml")
    
    if not workflow_path.exists():
        print(f"⚠️  WARNING: {workflow_path} not found")
        return True  # Not a hard failure
    
    content = workflow_path.read_text()
    
    # Check that workflow uses ACTIVE_PROMPT=signals
    if "ACTIVE_PROMPT=digest" in content:
        print("❌ ERROR: Workflow must use ACTIVE_PROMPT=signals, not digest")
        return False
    
    if "ACTIVE_PROMPT=signals" not in content:
        print("⚠️  WARNING: Workflow should explicitly set ACTIVE_PROMPT=signals")
        # Not a hard failure since default is now signals
    
    print("✓ Workflow uses signals format")
    return True

def check_recent_files():
    """Check that recently created/modified files are signals format, not digest."""
    import time
    from datetime import datetime, timedelta
    
    writeup_dir = Path("writeup")
    
    if not writeup_dir.exists():
        print("⚠️  WARNING: writeup/ directory not found - skipping file check")
        return True
    
    # Only check files modified in the last 24 hours (newly created)
    # Historical digest files are allowed to exist
    cutoff_time = time.time() - (24 * 60 * 60)  # 24 hours ago
    
    digest_files = []
    for f in writeup_dir.rglob("digest_*.md"):
        try:
            mtime = f.stat().st_mtime
            if mtime > cutoff_time:
                digest_files.append(f)
        except (OSError, AttributeError):
            # File might not exist or be accessible
            continue
    
    if digest_files:
        print(f"❌ ERROR: Found {len(digest_files)} recently created/modified digest format files (DEPRECATED):")
        for f in digest_files[:5]:  # Show first 5
            mod_time = datetime.fromtimestamp(f.stat().st_mtime)
            print(f"   - {f} (modified: {mod_time.strftime('%Y-%m-%d %H:%M')})")
        if len(digest_files) > 5:
            print(f"   ... and {len(digest_files) - 5} more")
        print("   Digest format is DEPRECATED - only signals format should be generated")
        return False
    
    print("✓ No recently created digest format files found")
    return True

def main():
    """Run all validation checks."""
    print("🔍 Validating signals-only format (digest is DEPRECATED)...")
    print()
    
    checks = [
        ("Template defaults", check_template_defaults),
        ("No digest generation", check_no_digest_generation),
        ("Recent files", check_recent_files),
    ]
    
    all_passed = True
    for name, check_func in checks:
        print(f"Checking {name}...")
        if not check_func():
            all_passed = False
        print()
    
    if all_passed:
        print("✅ All validation checks passed - signals format enforced")
        return 0
    else:
        print("❌ Validation failed - digest format must not be used")
        return 1

if __name__ == "__main__":
    sys.exit(main())
