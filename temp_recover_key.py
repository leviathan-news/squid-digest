#!/usr/bin/env python3
"""
TEMPORARY SCRIPT TO RECOVER GHOST_ADMIN_API_KEY FROM GITHUB SECRETS
⚠️ DELETE THIS FILE IMMEDIATELY AFTER USE ⚠️
"""

import os
import base64
import hashlib
from cryptography.fernet import Fernet

def encrypt_key(key: str, salt: str) -> str:
    """Encrypt the API key using the salt."""
    # Create a key from the salt
    key_bytes = hashlib.sha256(salt.encode()).digest()
    fernet = Fernet(base64.urlsafe_b64encode(key_bytes))
    
    # Encrypt the API key
    encrypted_key = fernet.encrypt(key.encode())
    return base64.urlsafe_b64encode(encrypted_key).decode()

def main():
    print("=" * 60)
    print("🚨 TEMPORARY GHOST API KEY RECOVERY SCRIPT 🚨")
    print("=" * 60)
    print()
    
    # Check if we're in GitHub Actions environment
    if os.getenv("GITHUB_ACTIONS"):
        print("✅ Running in GitHub Actions environment")
        ghost_key = os.getenv("GHOST_ADMIN_API_KEY")
        salt = os.getenv("RECOVERY_SALT")
        
        if ghost_key and salt:
            print("✅ GHOST_ADMIN_API_KEY and RECOVERY_SALT found!")
            print()
            
            # Encrypt the key
            encrypted_key = encrypt_key(ghost_key, salt)
            
            print("🔐 Encrypted Ghost Admin API Key:")
            print("-" * 60)
            print(encrypted_key)
            print("-" * 60)
            print()
            print("🔑 To decrypt, use this Python code:")
            print("-" * 60)
            print(f"""
import base64
import hashlib
from cryptography.fernet import Fernet

def decrypt_key(encrypted_key: str, salt: str) -> str:
    key_bytes = hashlib.sha256(salt.encode()).digest()
    fernet = Fernet(base64.urlsafe_b64encode(key_bytes))
    decrypted = fernet.decrypt(base64.urlsafe_b64decode(encrypted_key))
    return decrypted.decode()

# Your encrypted key:
encrypted_key = "{encrypted_key}"

# Your salt (set this in your local environment):
salt = "YOUR_SALT_HERE"

# Decrypt:
decrypted_key = decrypt_key(encrypted_key, salt)
print(decrypted_key)
""")
            print("-" * 60)
            print()
            print("⚠️  COPY THE ENCRYPTED KEY AND DECRYPTION CODE NOW!")
            print("⚠️  DELETE THIS SCRIPT IMMEDIATELY AFTER USE!")
        elif not ghost_key:
            print("❌ GHOST_ADMIN_API_KEY not found in GitHub environment")
        elif not salt:
            print("❌ RECOVERY_SALT not found in GitHub environment")
            print("Add RECOVERY_SALT to your GitHub secrets first!")
    else:
        print("❌ Not running in GitHub Actions environment")
        print("This script only works when run in GitHub Actions")
        print()
        print("To use this script:")
        print("1. Add RECOVERY_SALT to your GitHub secrets")
        print("2. Commit this script to your repository")
        print("3. Create a temporary GitHub Action workflow")
        print("4. Run the workflow to get the encrypted key")
        print("5. Delete this script immediately after")
    
    print()
    print("=" * 60)
    print("⚠️  DELETE THIS FILE IMMEDIATELY AFTER USE ⚠️")
    print("=" * 60)

if __name__ == "__main__":
    main()
