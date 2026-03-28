"""
Tests for distribution helpers: compact price formatting, tweet building,
broadcast caption building, caption truncation, and blurb generation.
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestFormatCompactPrice:
    """Tests for _format_compact_price in post_x.py and post_telegram_broadcast.py."""

    def _fmt(self, price):
        from post_x import _format_compact_price
        return _format_compact_price(price)

    def test_large_round(self):
        assert self._fmt(71400) == "$71K"

    def test_large_with_decimal(self):
        assert self._fmt(100000) == "$100K"

    def test_thousands(self):
        assert self._fmt(2179) == "$2.2K"

    def test_exact_thousand(self):
        assert self._fmt(1000) == "$1.0K"

    def test_hundreds(self):
        assert self._fmt(105.18) == "$105"

    def test_near_hundred_no_scientific(self):
        """99.9 must NOT produce scientific notation like $1e+02."""
        result = self._fmt(99.9)
        assert "e" not in result, f"Scientific notation detected: {result}"
        assert result == "$99.9"

    def test_tens(self):
        assert self._fmt(10.5) == "$10.5"

    def test_single_digit(self):
        assert self._fmt(1.5) == "$1.50"

    def test_sub_dollar(self):
        assert self._fmt(0.458) == "$0.46"

    def test_very_small(self):
        assert self._fmt(0.001) == "$0.00"

    def test_near_ten(self):
        assert self._fmt(9.99) == "$9.99"


class TestExtractMarketStats:
    """Tests for _extract_market_stats against actual signal file format."""

    SAMPLE_CONTENT = """## 💰 Market Snapshot (24h)
• 🟢 **[BTC](https://leviathannews.xyz/t/216/BTC)**: $71,400.00 (+2.15%)
• 🟢 **[ETH](https://leviathannews.xyz/t/227/ETH)**: $2,179.80 (+2.27%)
• 🟢 **[OPEN](https://leviathannews.xyz/t/821/OPEN)**: $0.4580 (+3.33%)

**📈 Top Gainers:**
• 🟢 **[ENA](https://leviathannews.xyz/t/707/ENA)**: $0.0990 (+7.1%)
"""

    def test_extracts_three_stats(self):
        from post_x import _extract_market_stats
        stats = _extract_market_stats(self.SAMPLE_CONTENT)
        assert len(stats) == 3

    def test_first_stat_is_btc(self):
        from post_x import _extract_market_stats
        stats = _extract_market_stats(self.SAMPLE_CONTENT)
        symbol, price, pct_str, pct_float = stats[0]
        assert symbol == "BTC"
        assert price == 71400.0
        assert pct_str == "+2.15%"
        assert pct_float == 2.15

    def test_sub_dollar_price_parsed(self):
        from post_x import _extract_market_stats
        stats = _extract_market_stats(self.SAMPLE_CONTENT)
        _, price, _, _ = stats[2]  # OPEN
        assert price == 0.458

    def test_negative_percentages(self):
        content = '• 🔴 **[BTC](url)**: $66,324.00 (-4.78%)'
        from post_x import _extract_market_stats
        stats = _extract_market_stats(content)
        assert stats[0][3] == -4.78


class TestBuildTweet:
    """Tests for tweet building and progressive trimming."""

    def _build(self, blurb="Test blurb", stats_content=None):
        from post_x import _build_tweet, EFFECTIVE_CHAR_LIMIT, X_TCO_URL_LENGTH
        date = datetime(2026, 3, 27)
        content = stats_content or (
            '• 🟢 **[BTC](url)**: $71,400.00 (+2.15%)\n'
            '• 🟢 **[ETH](url)**: $2,179.80 (+2.27%)\n'
            '• 🟢 **[OPEN](url)**: $0.4580 (+3.33%)\n'
        )
        url = "https://digest.leviathannews.xyz/leviathan-news-daily-digest-march-27-2026/"
        tweet = _build_tweet(date, content, url, blurb)
        real_len = len(tweet) - len(url) + X_TCO_URL_LENGTH
        return tweet, real_len

    def test_within_budget(self):
        from post_x import EFFECTIVE_CHAR_LIMIT
        _, real_len = self._build(blurb="Short blurb here")
        assert real_len <= EFFECTIVE_CHAR_LIMIT

    def test_contains_branding(self):
        tweet, _ = self._build()
        assert "SQUID DIGEST" in tweet

    def test_contains_cta(self):
        tweet, _ = self._build()
        assert "Read the full digest at" in tweet

    def test_long_blurb_trims_stats(self):
        """A long blurb should cause stats to be dropped before the blurb is truncated."""
        tweet, real_len = self._build(blurb="A" * 200)
        from post_x import EFFECTIVE_CHAR_LIMIT
        assert real_len <= EFFECTIVE_CHAR_LIMIT

    def test_no_stats_content(self):
        """Tweet should work even with no market stats."""
        tweet, real_len = self._build(stats_content="no stats here")
        from post_x import EFFECTIVE_CHAR_LIMIT
        assert real_len <= EFFECTIVE_CHAR_LIMIT
        assert "Read the full digest at" in tweet


class TestTruncateCaption:
    """Tests for TelegramClient._truncate_caption."""

    def _truncate(self, html, max_len):
        from squid_digest.telegram.client import TelegramClient
        return TelegramClient._truncate_caption(html, max_len)

    def test_short_content_unchanged(self):
        assert self._truncate("hello", 1024) == "hello"

    def test_hard_cap_enforced(self):
        result = self._truncate("a" * 2000, 1024)
        assert len(result) <= 1024

    def test_closes_open_tags(self):
        html = '<b>bold text that is very long ' + 'x' * 1000 + '</b>'
        result = self._truncate(html, 200)
        assert result.endswith('</b>')
        assert len(result) <= 200

    def test_handles_nested_tags(self):
        html = '<b><i>nested ' + 'x' * 1000 + '</i></b>'
        result = self._truncate(html, 300)
        assert '</i>' in result
        assert '</b>' in result
        assert len(result) <= 300

    def test_no_truncation_notice(self):
        """Caption truncation should NOT add [Message truncated...] (unlike message truncation)."""
        html = 'a' * 2000
        result = self._truncate(html, 1024)
        assert "truncated" not in result.lower()

    def test_does_not_cut_inside_tag(self):
        """Should not leave a broken tag like '<b' without '>'."""
        html = 'text <b>bold</b> more text ' + 'x' * 1000
        result = self._truncate(html, 50)
        # Count < and > — should be balanced
        assert result.count('<') == result.count('>')


class TestBroadcastCaption:
    """Tests for _build_caption in post_telegram_broadcast.py."""

    def _build(self, meta=None, content=None):
        from post_telegram_broadcast import _build_caption, CAPTION_LIMIT
        date = datetime(2026, 3, 27)
        meta = meta or {
            "blurb": "Test blurb about crypto markets",
            "top_story_headline": "Major exchange launches new feature",
            "top_story_comment": "This is a great development for the ecosystem",
            "top_story_author": "CryptoUser",
        }
        content = content or (
            '• 🟢 **[BTC](url)**: $71,400.00 (+2.15%)\n'
            '• 🟢 **[ETH](url)**: $2,179.80 (+2.27%)\n'
            '• 🟢 **[OPEN](url)**: $0.4580 (+3.33%)\n'
        )
        url = "https://example.com/digest"
        return _build_caption(date, meta, content, url), CAPTION_LIMIT

    def test_within_limit(self):
        caption, limit = self._build()
        assert len(caption) <= limit

    def test_contains_branding(self):
        caption, _ = self._build()
        assert "SQUID DIGEST" in caption

    def test_contains_blurb(self):
        caption, _ = self._build()
        assert "Test blurb" in caption

    def test_contains_top_story(self):
        caption, _ = self._build()
        assert "Major exchange" in caption

    def test_contains_clickable_links(self):
        caption, _ = self._build()
        assert '<a href="' in caption

    def test_html_escapes_user_content(self):
        """User content with & < > should be escaped."""
        meta = {
            "blurb": "Token A & B <rise>",
            "top_story_headline": "Price > $100 & climbing",
            "top_story_comment": "Great <stuff>!",
            "top_story_author": "User&Name",
        }
        caption, _ = self._build(meta=meta)
        assert "&amp;" in caption
        assert "&lt;" in caption
        assert "&gt;" in caption

    def test_empty_meta_still_builds(self):
        caption, limit = self._build(meta={})
        assert len(caption) <= limit
        assert "SQUID DIGEST" in caption


class TestGenerateBlurb:
    """Tests for generate_blurb fallback chain (without Perplexity API)."""

    def _generate_no_api(self, headlines):
        """Call generate_blurb with API key disabled to test template fallback."""
        from unittest.mock import patch
        from squid_digest.config import generate_blurb
        # Patch the config dict to remove API key, forcing template fallback
        with patch.dict("squid_digest.config.PERPLEXITY_CHAT_MODEL", {"API_KEY": None}):
            return generate_blurb(headlines)

    def test_empty_headlines_returns_default(self):
        from squid_digest.config import generate_blurb, DEFAULT_BLURB
        assert generate_blurb([]) == DEFAULT_BLURB

    def test_three_headlines_template(self):
        result = self._generate_no_api(["Headline A rises", "Headline B falls", "Headline C launches"])
        assert "In today's digest:" in result
        assert "Headline A" in result
        assert "Headline C" in result

    def test_two_headlines_template(self):
        result = self._generate_no_api(["First story", "Second story"])
        assert "In today's digest:" in result
        assert "and" in result

    def test_single_headline_template(self):
        result = self._generate_no_api(["Only headline"])
        assert "In today's digest:" in result
        assert "Only headline" in result
