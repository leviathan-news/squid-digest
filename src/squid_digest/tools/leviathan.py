"""Client for Leviathan News API."""

import requests, json, re
from typing import List, Dict, Any
from pathlib import Path
from langchain_community.document_loaders import WebBaseLoader


def get_redirect_url(url: str) -> str:
    """
    Get the final redirect URL after following all redirects, including meta refresh redirects.

    Args:
        url (str): The URL to follow redirects for

    Returns:
        str: The final URL after all redirects, or None if there's an error
    """
    try:
        # First try standard HTTP redirects
        response = requests.get(url, allow_redirects=True, timeout=30)

        # Check if the response contains a meta refresh redirect
        if (
            'meta http-equiv="refresh"' in response.text
            or "meta http-equiv='refresh'" in response.text
        ):
            import re

            # Look for meta refresh redirects
            meta_refresh_pattern = r'<meta\s+http-equiv=["\']?refresh["\']?\s+content=["\']?\d+;\s*url=([^"\'>\s]+)["\']?'
            match = re.search(meta_refresh_pattern, response.text, re.IGNORECASE)

            if match:
                redirect_url = match.group(1)
                # Handle relative URLs
                if redirect_url.startswith("/"):
                    from urllib.parse import urlparse

                    parsed = urlparse(url)
                    redirect_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
                elif not redirect_url.startswith("http"):
                    from urllib.parse import urlparse

                    parsed = urlparse(url)
                    redirect_url = f"{parsed.scheme}://{parsed.netloc}/{redirect_url}"

                response = requests.get(
                    redirect_url, allow_redirects=True, timeout=30, verify=False
                )

        return response.url

    except requests.exceptions.TooManyRedirects:
        print(f"Too many redirects for URL: {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error following redirects for {url}: {e}")
        return None


def clean_excessive_newlines(text):
    """Remove excessive newlines, keeping at most 1 consecutive newlines"""
    # Replace 2 or more consecutive newlines with just 1 newlines
    cleaned = re.sub(r"\n{2,}", "\n", text)
    return cleaned


class LeviathanNewsFetcher:
    """Fetches news from Leviathan News API."""

    BASE_URL = "https://api.leviathannews.xyz/api/v1/news/"
    SAVE_DIR = Path(".data")
    SAVE_DIR.mkdir(exist_ok=True)

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def fetch_news(self, limit: int = 10, save: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch top news items sorted by hot/trending.

        Args:
            limit: Number of news items to fetch

        Returns:
            List of news items with headline, source, url, tags

        Raises:
            requests.HTTPError: If API request fails
        """
        params = {"sort_type": "hot", "sort_timeframe": 1}

        response = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        # Handle different response formats
        if isinstance(data, list):
            news = data[:limit]
        else:
            news = data.get("results")[:limit] or data.get("items")[:limit] or []
        if save:
            with open(self.SAVE_DIR / "leviathan_news.json", "w") as f:
                json.dump(news, f)
        return news

    def get_redirect_url(
        self, news: List[Dict[str, Any]], save: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get the redirect URL for a top news item.
        """
        news_with_redirect_url = []
        for item in news:
            _id = item["id"]
            _url = item["url"]
            redirect_url = get_redirect_url(_url)

            news_with_redirect_url.append(
                {
                    "id": _id,
                    "url": _url,
                    "redirect_url": redirect_url,
                }
            )
        if save:
            with open(self.SAVE_DIR / "leviathan_news_redirect_url.json", "w") as f:
                json.dump(news_with_redirect_url, f)
        return news_with_redirect_url

    def fetch_news_content(
        self, news_with_redirect_url: List[Dict[str, Any]], save: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch news content from Leviathan News API.
        """
        urls = [
            item["redirect_url"]
            for item in news_with_redirect_url
            if item["redirect_url"]
        ]
        loader = WebBaseLoader(urls)
        loader.requests_per_second = 1
        loader.requests_kwargs = {"verify": False}
        docs = loader.load()
        news_with_content = [
            {
                "id": item["id"],
                "content": clean_excessive_newlines(doc.page_content),
                "title": doc.metadata.get("title", ""),
                "description": clean_excessive_newlines(
                    doc.metadata.get("description", "")
                ),
            }
            for item, doc in zip(news_with_redirect_url, docs)
        ]
        if save:
            with open(self.SAVE_DIR / "leviathan_news_content.json", "w") as f:
                json.dump(news_with_content, f)
        return news_with_content
