"""Minimal X (Twitter) API v2 client for posting digest tweets.

Uses OAuth 1.0a User Context via requests-oauthlib. Posting, bounded
idempotency reads, outcome reads, and a non-posting identity diagnostic share
the same narrow client.
"""

import os
import re
from typing import Any, Optional

import requests
from requests_oauthlib import OAuth1Session


_API_BASE = "https://api.x.com/2"
_MAX_DIAGNOSTIC_TEXT = 320
_SENSITIVE_VALUE = re.compile(
    r"(?ix)\b(?:authorization\s*:\s*bearer|bearer|"
    r"oauth[ _-]?(?:token|signature)|access[ _-]?token|"
    r"api[ _-]?key|client[ _-]?secret|secret)"
    r"(?:\s*[:=]\s*|\s+)[^\s,;]+"
)


def _safe_diagnostic_text(value: object) -> Optional[str]:
    """Return bounded provider text without echoing a credential-shaped value."""
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str):
        return None
    redacted = _SENSITIVE_VALUE.sub("[REDACTED]", value)
    return redacted[:_MAX_DIAGNOSTIC_TEXT]


def _error_diagnostic(response: Any) -> dict[str, object]:
    """Project a failed X response to a small, safe-to-log diagnostic."""
    diagnostic: dict[str, object] = {"status": int(response.status_code)}
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return diagnostic

    if not isinstance(payload, dict):
        return diagnostic

    for key in ("title", "type", "detail", "code"):
        value = _safe_diagnostic_text(payload.get(key))
        if value:
            diagnostic[key] = value

    errors = payload.get("errors")
    if isinstance(errors, list):
        projected = []
        for error in errors[:3]:
            if not isinstance(error, dict):
                continue
            row = {}
            for key in ("title", "type", "detail", "code"):
                value = _safe_diagnostic_text(error.get(key))
                if value:
                    row[key] = value
            if row:
                projected.append(row)
        if projected:
            diagnostic["errors"] = projected
    return diagnostic


class XAPIError(RuntimeError):
    """A failed X response whose public diagnostic is safe to emit in CI logs."""

    def __init__(self, operation: str, diagnostic: dict[str, object]):
        self.operation = operation
        self.diagnostic = diagnostic
        title = diagnostic.get("title") or diagnostic.get("type") or "X API error"
        super().__init__(
            f"{operation} failed (status={diagnostic.get('status', 'unknown')}; {title})"
        )


class XClient:
    """Lightweight X API v2 client.

    All four OAuth 1.0a credentials default to environment variables
    when not provided explicitly.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("X_API_KEY")
        self.api_secret = api_secret or os.getenv("X_API_SECRET")
        self.access_token = access_token or os.getenv("X_ACCESS_TOKEN")
        self.access_token_secret = access_token_secret or os.getenv("X_ACCESS_TOKEN_SECRET")

        if not all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
            raise ValueError(
                "X API credentials required.  Set X_API_KEY, X_API_SECRET, "
                "X_ACCESS_TOKEN, and X_ACCESS_TOKEN_SECRET environment variables."
            )

        self._session = OAuth1Session(
            self.api_key,
            client_secret=self.api_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret,
        )

    def post_tweet(self, text: str, *, in_reply_to_tweet_id: Optional[str] = None) -> dict:
        """Post a tweet and return the API response JSON.

        Raises on HTTP errors (429 rate-limit, 403 cap exceeded, etc.).
        """
        payload = {"text": text}
        if in_reply_to_tweet_id:
            payload['reply'] = {'in_reply_to_tweet_id': str(in_reply_to_tweet_id)}
        resp = self._session.post(f"{_API_BASE}/tweets", json=payload, timeout=30)
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise XAPIError("post_tweet", _error_diagnostic(resp)) from exc
        return resp.json()

    def diagnose_authenticated_user(self) -> dict[str, object]:
        """Perform one non-posting OAuth identity check with safe error evidence.

        This intentionally does not test write authorization: diagnostics must not
        create, reply to, or delete an X post.
        """
        try:
            response = self._session.get(
                f"{_API_BASE}/users/me",
                params={"user.fields": "id,name,username"},
                timeout=30,
            )
        except requests.RequestException as exc:
            return {
                "ok": False,
                "operation": "get_authenticated_user",
                "failure_class": type(exc).__name__,
            }

        if not response.ok:
            return {
                "ok": False,
                "operation": "get_authenticated_user",
                **_error_diagnostic(response),
            }

        try:
            data = response.json().get("data", {})
        except (TypeError, ValueError):
            return {
                "ok": False,
                "operation": "get_authenticated_user",
                "status": int(response.status_code),
                "failure_class": "InvalidJSON",
            }
        if not isinstance(data, dict) or not data.get("id") or not data.get("username"):
            return {
                "ok": False,
                "operation": "get_authenticated_user",
                "status": int(response.status_code),
                "failure_class": "UnexpectedIdentityPayload",
            }
        return {
            "ok": True,
            "operation": "get_authenticated_user",
            "status": int(response.status_code),
            "account": {"id": str(data["id"]), "username": str(data["username"])},
        }

    def search_recent(self, query: str, start_time: Optional[str] = None) -> list:
        """Search recent tweets (last 7 days).

        Returns a list of tweet dicts, or ``[]`` on failure (fail-open
        so that a flaky search does not block posting).

        Args:
            query: Search query string (e.g. ``from:handle url:"…"``)
            start_time: ISO 8601 timestamp to restrict results
        """
        params = {"query": query, "max_results": 10, "tweet.fields": "created_at,referenced_tweets,note_tweet"}
        if start_time:
            params["start_time"] = start_time

        try:
            resp = self._session.get(f"{_API_BASE}/tweets/search/recent", params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                rows = data.get("data", [])
                for row in rows:
                    row['text'] = row.get('note_tweet', {}).get('text') or row.get('text', '')
                return rows
            # Non-200 → fail open
            print(f"⚠ X search returned {resp.status_code}, proceeding anyway")
            return []
        except Exception as e:
            print(f"⚠ X search failed ({e}), proceeding anyway")
            return []

    def get_posts(self, post_ids: list[str]) -> list[dict]:
        """Fetch owned-post engagement snapshots in one bounded request."""
        ids = [str(value) for value in post_ids if value]
        if not ids or len(ids) > 100:
            raise ValueError("get_posts requires between 1 and 100 IDs")
        resp = self._session.get(
            f"{_API_BASE}/tweets",
            params={
                "ids": ",".join(ids),
                "tweet.fields": "created_at,public_metrics,non_public_metrics,organic_metrics",
            },
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        rows = body.get("data", [])
        if not isinstance(rows, list):
            raise RuntimeError("X metrics response has no data list")
        return rows
