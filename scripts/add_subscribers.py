#!/usr/bin/env python3
"""
Quick script to add email subscribers to Ghost for testing.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path so we can import squid_digest
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

load_dotenv()

from squid_digest.email import GhostEmailClient

def main():
    client = GhostEmailClient()
    
    # Add admin email as subscriber
    admin_emails = os.getenv("ADMIN_EMAILS", "ghall1@gmail.com").split(",")
    public_emails = os.getenv("PUBLIC_EMAILS", "ghall1@gmail.com,curvedefi@gmail.com").split(",")
    
    all_emails = list(set(admin_emails + public_emails))
    
    print(f"Adding {len(all_emails)} emails as Ghost subscribers...")
    
    for email in all_emails:
        email = email.strip()
        if email:
            try:
                # Create subscriber with admin label
                member = client.create_member(email, labels=["admin", "subscriber"])
                print(f"✓ Added {email} as subscriber (ID: {member.get('id', 'unknown')})")
            except Exception as e:
                print(f"✗ Failed to add {email}: {e}")

if __name__ == "__main__":
    main()

