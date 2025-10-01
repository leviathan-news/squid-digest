"""Client for Leviathan News API."""
import httpx
from typing import List, Dict, Any


class LeviathanNewsClient:
    """Fetches news from Leviathan News API."""

    BASE_URL = "https://api.leviathannews.xyz/api/v1/news/"

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def fetch_top_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch top news items sorted by hot/trending.

        Args:
            limit: Number of news items to fetch

        Returns:
            List of news items with headline, source, url, tags

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        params = {
            "limit": limit,
            "sort_type": "hot",
            "sort_timeframe": 1
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        # Handle different response formats
        if isinstance(data, list):
            return data
        return data.get("results") or data.get("items") or []
