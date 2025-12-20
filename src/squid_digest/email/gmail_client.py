"""Gmail API client for reading Substack verification codes.

Uses Google Service Account with domain-wide delegation to read emails
from a Google Workspace account without user interaction.
"""

import base64
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GmailClient:
    """Client for reading emails via Gmail API with service account.

    Requires:
    1. Google Cloud project with Gmail API enabled
    2. Service account with domain-wide delegation
    3. Google Workspace admin granting the service account access
       to scope: https://www.googleapis.com/auth/gmail.readonly
    """

    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def __init__(
        self,
        service_account_json: Optional[str] = None,
        impersonate_email: Optional[str] = None
    ):
        """Initialize Gmail client.

        Args:
            service_account_json: JSON string containing service account credentials.
                                  If None, reads from GOOGLE_SERVICE_ACCOUNT_JSON env var.
            impersonate_email: Email to impersonate (required for domain-wide delegation).
                               If None, reads from GMAIL_IMPERSONATE_EMAIL env var.

        Raises:
            ValueError: If credentials are missing or invalid.
        """
        self.service_account_json = service_account_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        self.impersonate_email = impersonate_email or os.getenv("GMAIL_IMPERSONATE_EMAIL")

        if not self.service_account_json:
            raise ValueError(
                "Service account credentials required. "
                "Set GOOGLE_SERVICE_ACCOUNT_JSON environment variable."
            )

        if not self.impersonate_email:
            raise ValueError(
                "Impersonate email required for domain-wide delegation. "
                "Set GMAIL_IMPERSONATE_EMAIL environment variable."
            )

        self.service = self._build_service()

    def _build_service(self):
        """Build Gmail API service with service account credentials."""
        try:
            credentials_info = json.loads(self.service_account_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in service account credentials: {e}")

        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=self.SCOPES,
            subject=self.impersonate_email
        )

        return build('gmail', 'v1', credentials=credentials)

    def get_substack_verification_code(
        self,
        max_age_seconds: int = 120,
        poll_interval_seconds: int = 5,
        max_attempts: int = 24
    ) -> Optional[str]:
        """Poll for Substack verification code email and extract the code.

        Args:
            max_age_seconds: Only consider emails received within this many seconds.
            poll_interval_seconds: How often to check for new emails.
            max_attempts: Maximum number of polling attempts.

        Returns:
            The 6-digit verification code if found, None otherwise.
        """
        print(f"Polling for Substack verification email (max {max_attempts} attempts)...")

        for attempt in range(max_attempts):
            code = self._check_for_verification_code(max_age_seconds)
            if code:
                print(f"Found verification code: {code}")
                return code

            if attempt < max_attempts - 1:
                print(f"  Attempt {attempt + 1}/{max_attempts}: No code yet, waiting {poll_interval_seconds}s...")
                time.sleep(poll_interval_seconds)

        print("Failed to find verification code within timeout")
        return None

    def _check_for_verification_code(self, max_age_seconds: int) -> Optional[str]:
        """Check inbox for recent Substack verification email.

        Args:
            max_age_seconds: Only consider emails from the last N seconds.

        Returns:
            The verification code if found, None otherwise.
        """
        try:
            # Calculate timestamp threshold
            threshold = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
            after_timestamp = int(threshold.timestamp())

            # Search for recent Substack emails
            # Substack sends from no-reply@substack.com or similar
            query = f'from:substack.com after:{after_timestamp}'

            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=5
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                return None

            # Check each message for verification code
            for msg in messages:
                message = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()

                code = self._extract_code_from_message(message)
                if code:
                    return code

            return None

        except HttpError as e:
            print(f"Gmail API error: {e}")
            return None
        except Exception as e:
            print(f"Error checking Gmail: {e}")
            return None

    def _extract_code_from_message(self, message: dict) -> Optional[str]:
        """Extract verification code from email message.

        Args:
            message: Gmail API message object.

        Returns:
            The 6-digit code if found, None otherwise.
        """
        # Get subject to verify it's a verification email
        headers = message.get('payload', {}).get('headers', [])
        subject = next(
            (h['value'] for h in headers if h['name'].lower() == 'subject'),
            ''
        )

        # Check if this looks like a verification email
        verification_keywords = ['code', 'verify', 'confirm', 'login', 'sign in']
        if not any(kw in subject.lower() for kw in verification_keywords):
            # Also check body if subject doesn't match
            pass  # Continue to check body anyway

        # Get email body
        payload = message.get('payload', {})
        body_text = self._get_email_body(payload)

        if not body_text:
            return None

        # Look for 6-digit verification code using various patterns
        patterns = [
            # "Your code is 123456" or "code: 123456"
            r'(?:your\s+)?(?:verification\s+)?code\s*(?:is)?:?\s*(\d{6})\b',
            # "Enter 123456" or "enter the code 123456"
            r'enter\s+(?:the\s+)?(?:code\s+)?(\d{6})\b',
            # Standalone 6-digit number (fallback - less reliable)
            r'\b(\d{6})\b',
        ]

        for pattern in patterns:
            match = re.search(pattern, body_text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _get_email_body(self, payload: dict) -> str:
        """Extract text body from email payload.

        Handles both simple messages and multipart MIME.

        Args:
            payload: Gmail API message payload.

        Returns:
            Combined text content from the email.
        """
        body_text = ""

        # Handle simple body
        if 'body' in payload and 'data' in payload['body']:
            body_text = base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8', errors='ignore')

        # Handle multipart messages
        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')

                # Get text from text/plain or text/html parts
                if mime_type in ('text/plain', 'text/html'):
                    if 'body' in part and 'data' in part['body']:
                        part_text = base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8', errors='ignore')
                        body_text += " " + part_text

                # Recurse into nested multipart
                if 'parts' in part:
                    body_text += " " + self._get_email_body(part)

        return body_text


def test_gmail_client():
    """Test the Gmail client connection and email reading.

    Run with:
        python -c "from squid_digest.email.gmail_client import test_gmail_client; test_gmail_client()"
    """
    print("Testing Gmail client...")

    try:
        client = GmailClient()
        print(f"Gmail client initialized for: {client.impersonate_email}")

        # Try to list recent emails as a connection test
        results = client.service.users().messages().list(
            userId='me',
            maxResults=5
        ).execute()

        messages = results.get('messages', [])
        print(f"Connection successful! Found {len(messages)} recent messages.")

        # Show subjects of recent emails
        for msg in messages[:3]:
            message = client.service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='metadata',
                metadataHeaders=['Subject', 'From']
            ).execute()
            headers = {h['name']: h['value'] for h in message.get('payload', {}).get('headers', [])}
            print(f"  - From: {headers.get('From', 'Unknown')[:50]}")
            print(f"    Subject: {headers.get('Subject', 'No subject')[:60]}")

        return True

    except ValueError as e:
        print(f"Configuration error: {e}")
        return False
    except HttpError as e:
        print(f"Gmail API error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
