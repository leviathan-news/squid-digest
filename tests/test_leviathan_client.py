"""Tests for LeviathanNewsClient."""

import pytest
import httpx
from unittest.mock import patch, Mock
from squid_digest.clients.leviathan import LeviathanNewsClient


class TestLeviathanNewsClient:
    """Test cases for LeviathanNewsClient."""

    def test_fetch_top_news_real_api(self):
        """Test news fetching with real API call."""
        client = LeviathanNewsClient(timeout=10)

        # Make real API call
        result = client.fetch_top_news(limit=3)

        # Verify the result structure
        assert isinstance(result, list)
        # Now that we slice the results on the client side, limit should work
        assert len(result) <= 3  # Should not exceed requested limit

        # If we got results, verify they have expected structure based on actual API response
        if result:
            news_item = result[0]
            assert isinstance(news_item, dict)

            # Check for required fields based on actual API response
            assert "id" in news_item
            assert "headline" in news_item
            assert "source" in news_item
            assert "url" in news_item
            assert "date_posted" in news_item
            assert "tags" in news_item
            assert "content_type" in news_item

            # Verify field types
            assert isinstance(news_item["id"], int)
            assert isinstance(news_item["headline"], str)
            assert isinstance(news_item["source"], str)
            assert isinstance(news_item["url"], str)
            assert isinstance(news_item["tags"], list)
            assert news_item["content_type"] == "news"

            # Check tags structure
            if news_item["tags"]:
                tag = news_item["tags"][0]
                assert "id" in tag
                assert "name" in tag
                assert "slug" in tag
                assert isinstance(tag["id"], int)
                assert isinstance(tag["name"], str)
                assert isinstance(tag["slug"], str)
