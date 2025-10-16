#!/usr/bin/env python3
"""
TEMPORARY SCRIPT TO RECOVER GHOST_ADMIN_API_KEY FROM GITHUB SECRETS
⚠️ DELETE THIS FILE IMMEDIATELY AFTER USE ⚠️
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    print("=" * 60)
    print("🚨 TEMPORARY GHOST API KEY RECOVERY SCRIPT 🚨")
    print("=" * 60)
    print()
    
    # Check if we're in GitHub Actions environment
    if os.getenv("GITHUB_ACTIONS"):
        print("✅ Running in GitHub Actions environment")
        ghost_key = os.getenv("GHOST_ADMIN_API_KEY")
        if ghost_key:
            print("✅ GHOST_ADMIN_API_KEY found!")
            print()
            print("🔑 Your Ghost Admin API Key:")
            print("-" * 40)
            print(ghost_key)
            print("-" * 40)
            print()
            print("⚠️  COPY THIS KEY NOW - DELETE THIS SCRIPT IMMEDIATELY!")
        else:
            print("❌ GHOST_ADMIN_API_KEY not found in GitHub environment")
    else:
        print("❌ Not running in GitHub Actions environment")
        print("This script only works when run in GitHub Actions")
        print()
        print("To use this script:")
        print("1. Commit this script to your repository")
        print("2. Create a temporary GitHub Action workflow")
        print("3. Run the workflow to get the key")
        print("4. Delete this script immediately after")
    
    print()
    print("=" * 60)
    print("⚠️  DELETE THIS FILE IMMEDIATELY AFTER USE ⚠️")
    print("=" * 60)

if __name__ == "__main__":
    main()
