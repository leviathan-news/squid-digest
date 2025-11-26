"""Client for Leviathan News API."""

import requests, json, re
import time
import logging
from typing import List, Dict, Any
from pathlib import Path

# Optional import for WebBaseLoader (only needed for fetch_news_content)
try:
    from langchain_community.document_loaders import WebBaseLoader
except ImportError:
    WebBaseLoader = None  # type: ignore

logger = logging.getLogger(__name__)


def retry_request_with_backoff(func, max_retries=3, base_delay=1):
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
    
    Returns:
        Result of the function call
        
    Raises:
        The last exception if all retries fail
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, 
                requests.exceptions.ConnectionError) as e:
            if attempt == max_retries:
                logger.error(f"All {max_retries + 1} attempts failed. Last error: {e}")
                raise
            
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Attempt {attempt + 1} failed with {type(e).__name__}: {e}. "
                          f"Retrying in {delay} seconds...")
            time.sleep(delay)
        except Exception as e:
            # Don't retry for other types of errors
            logger.error(f"Non-retryable error: {e}")
            raise


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
    TOKEN_URL = "https://api.leviathannews.xyz/api/v1/token/"
    SQUID_PASS_WINNER_URL = "https://api.leviathannews.xyz/api/v1/squid-pass/winner/"
    SAVE_DIR = Path(".data")
    SAVE_DIR.mkdir(exist_ok=True)

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def fetch_news(self, limit: int = 10, save: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch top news items sorted by top/trending.

        Args:
            limit: Number of news items to fetch

        Returns:
            List of news items with headline, source, url, tags

        Raises:
            requests.HTTPError: If API request fails
        """
        params = {"sort_type": "top", "sort_timeframe": 1}

        def make_request():
            response = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        try:
            data = retry_request_with_backoff(make_request)
        except Exception as e:
            logger.error(f"Failed to fetch news after retries: {e}")
            # Try to load cached data as fallback
            cached_file = self.SAVE_DIR / "leviathan_news.json"
            if cached_file.exists():
                logger.warning("Using cached news data as fallback")
                with open(cached_file, "r") as f:
                    cached_data = json.load(f)
                return cached_data[:limit] if isinstance(cached_data, list) else []
            else:
                logger.error("No cached data available and API request failed")
                raise

        # Handle different response formats
        if isinstance(data, list):
            news = data[:limit]
        else:
            news = data.get("results")[:limit] or data.get("items")[:limit] or []
        if save:
            with open(self.SAVE_DIR / "leviathan_news.json", "w") as f:
                json.dump(news, f)
        return news

    def fetch_all_news_24h(self, save: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch ALL news items from the past 24 hours (not just top/limited).
        Useful for comprehensive review of all headlines.

        Args:
            save: Whether to save the results to cache file

        Returns:
            List of all news items from past 24 hours with headline, source, url, tags

        Raises:
            requests.HTTPError: If API request fails
        """
        all_news = []
        page = 1
        
        def fetch_page(page_num):
            params = {"sort_type": "top", "sort_timeframe": 1, "page": page_num}
            response = requests.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        
        try:
            # Fetch first page to get total_pages
            data = retry_request_with_backoff(lambda: fetch_page(page))
        except Exception as e:
            logger.error(f"Failed to fetch news after retries: {e}")
            # Try to load cached data as fallback
            cached_file = self.SAVE_DIR / "leviathan_news.json"
            if cached_file.exists():
                logger.warning("Using cached news data as fallback")
                with open(cached_file, "r") as f:
                    cached_data = json.load(f)
                return cached_data if isinstance(cached_data, list) else []
            else:
                logger.error("No cached data available and API request failed")
                raise
        
        # Handle different response formats
        if isinstance(data, list):
            all_news.extend(data)
            total_pages = 1  # If it's a list, assume single page
        else:
            all_news.extend(data.get("results", []) or data.get("items", []))
            total_pages = data.get("total_pages", 1)
        
        # Fetch remaining pages
        for page_num in range(2, total_pages + 1):
            try:
                data = retry_request_with_backoff(lambda: fetch_page(page_num))
                if isinstance(data, list):
                    all_news.extend(data)
                else:
                    all_news.extend(data.get("results", []) or data.get("items", []))
            except Exception as e:
                logger.warning(f"Failed to fetch page {page_num} of news: {e}. Continuing with available data.")
                break
        
        if save:
            with open(self.SAVE_DIR / "leviathan_news_24h.json", "w") as f:
                json.dump(all_news, f)
        
        return all_news

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
        if WebBaseLoader is None:
            raise ImportError(
                "langchain_community is required for fetch_news_content. "
                "Install it with: pip install langchain-community"
            )
        
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

    def fetch_tokens(self, save: bool = True) -> Dict[str, Any]:
        """
        Fetch all tracked tokens from Leviathan News API.
        
        Returns:
            Dictionary with token metadata including:
            - count: total number of tokens
            - total_pages: number of pages available
            - results: list of token data
        
        Raises:
            requests.HTTPError: If API request fails
        """
        all_tokens = []
        page = 1
        
        def fetch_page(page_num):
            response = requests.get(self.TOKEN_URL, params={"page": page_num}, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        
        try:
            # Fetch first page to get total_pages
            data = retry_request_with_backoff(lambda: fetch_page(page))
        except Exception as e:
            logger.error(f"Failed to fetch tokens after retries: {e}")
            # Try to load cached data as fallback
            cached_file = self.SAVE_DIR / "leviathan_tokens.json"
            if cached_file.exists():
                logger.warning("Using cached token data as fallback")
                with open(cached_file, "r") as f:
                    return json.load(f)
            else:
                logger.error("No cached token data available and API request failed")
                raise
        
        total_pages = data.get("total_pages", 1)
        all_tokens.extend(data.get("results", []))
        
        # Fetch remaining pages
        for page in range(2, total_pages + 1):
            try:
                data = retry_request_with_backoff(lambda: fetch_page(page))
                all_tokens.extend(data.get("results", []))
            except Exception as e:
                logger.warning(f"Failed to fetch page {page} of tokens: {e}. Continuing with available data.")
                break
        
        token_data = {
            "count": data.get("count", len(all_tokens)),
            "total_pages": total_pages,
            "tokens": all_tokens
        }
        
        if save:
            with open(self.SAVE_DIR / "leviathan_tokens.json", "w") as f:
                json.dump(token_data, f)
        
        return token_data

    def fetch_squid_pass_winner(self, save: bool = True) -> Dict[str, Any]:
        """
        Fetch the current SQUID Pass winner from Leviathan News API.
        
        Returns:
            Dictionary containing the squid_pass_winner data, or None if no winner exists.
            The structure matches the API response with a 'squid_pass_winner' key.
        
        Raises:
            requests.HTTPError: If API request fails
        """
        def make_request():
            response = requests.get(self.SQUID_PASS_WINNER_URL, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        try:
            data = retry_request_with_backoff(make_request)
        except Exception as e:
            logger.error(f"Failed to fetch SQUID Pass winner after retries: {e}")
            # Try to load cached data as fallback
            cached_file = self.SAVE_DIR / "leviathan_squid_pass_winner.json"
            if cached_file.exists():
                logger.warning("Using cached SQUID Pass winner data as fallback")
                with open(cached_file, "r") as f:
                    cached_data = json.load(f)
                return cached_data if cached_data.get("squid_pass_winner") else None
            else:
                logger.warning("No cached SQUID Pass winner data available and API request failed")
                return None

        # The API returns {"squid_pass_winner": {...}} or {"squid_pass_winner": null}
        if data.get("squid_pass_winner") is None:
            return None
        
        if save:
            with open(self.SAVE_DIR / "leviathan_squid_pass_winner.json", "w") as f:
                json.dump(data, f)
        
        return data
