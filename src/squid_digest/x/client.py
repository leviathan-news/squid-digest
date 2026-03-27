"""Minimal X (Twitter) API v2 client for posting digest tweets.

Uses OAuth 1.0a User Context via requests-oauthlib.  Only two
operations are needed: post a tweet and search recent tweets (for
idempotency checks).
"""

import os
from typing import Optional

from requests_oauthlib import OAuth1Session


_API_BASE = "https://api.x.com/2"


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

    def post_tweet(self, text: str) -> dict:
        """Post a tweet and return the API response JSON.

        Raises on HTTP errors (429 rate-limit, 403 cap exceeded, etc.).
        """
        resp = self._session.post(f"{_API_BASE}/tweets", json={"text": text})
        resp.raise_for_status()
        return resp.json()

    def search_recent(self, query: str, start_time: Optional[str] = None) -> list:
        """Search recent tweets (last 7 days).

        Returns a list of tweet dicts, or ``[]`` on failure (fail-open
        so that a flaky search does not block posting).

        Args:
            query: Search query string (e.g. ``from:handle url:"…"``)
            start_time: ISO 8601 timestamp to restrict results
        """
        params = {"query": query, "max_results": 10}
        if start_time:
            params["start_time"] = start_time

        try:
            resp = self._session.get(f"{_API_BASE}/tweets/search/recent", params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [])
            # Non-200 → fail open
            print(f"⚠ X search returned {resp.status_code}, proceeding anyway")
            return []
        except Exception as e:
            print(f"⚠ X search failed ({e}), proceeding anyway")
            return []
