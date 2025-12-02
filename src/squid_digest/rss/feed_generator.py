"""RSS feed generator for Squid Digest."""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import re
from feedgen.feed import FeedGenerator
from .digest_scanner import DigestFile


class RSSFeedGenerator:
    """Generate RSS 2.0 feed from digest markdown files."""

    def __init__(self, base_url: str = "https://raw.githubusercontent.com/leviathan-news/squid-digest/main/writeup"):
        """
        Initialize RSS feed generator.

        Args:
            base_url: Base URL for digest permalinks (GitHub raw URL)
        """
        self.base_url = base_url.rstrip('/')

        # Import GhostEmailClient for HTML conversion
        # Delay import to avoid circular dependencies
        try:
            from squid_digest.email.ghost_client import GhostEmailClient
            self.ghost_client = GhostEmailClient()
        except Exception as e:
            print(f"Warning: Could not import GhostEmailClient: {e}")
            print("HTML conversion will be limited to basic markdown rendering")
            self.ghost_client = None

    def generate_feed(
        self,
        digests: List[DigestFile],
        output_path: Path,
        feed_title: str = "Squid Digest - Crypto Trading Signals",
        feed_description: str = "AI-powered daily crypto trading signals from Leviathan News",
        feed_author: str = "Squid Digest",
        feed_link: Optional[str] = None
    ) -> int:
        """
        Generate RSS 2.0 feed from digest files.

        Args:
            digests: List of DigestFile objects to include
            output_path: Where to save the feed.xml file
            feed_title: RSS channel title
            feed_description: RSS channel description
            feed_author: RSS channel author
            feed_link: RSS channel link (defaults to base_url/feed.xml)

        Returns:
            Number of items added to feed
        """
        if not digests:
            raise ValueError("No digests provided for feed generation")

        # Create feed
        fg = FeedGenerator()
        fg.id(self.base_url)
        fg.title(feed_title)
        fg.link(href=feed_link or f"{self.base_url}/feed.xml", rel='alternate')
        fg.description(feed_description)
        fg.language('en-US')
        fg.author({'name': feed_author, 'email': 'squid@leviathannews.xyz'})

        # Add self link for feed discovery
        feed_url = f"{self.base_url}/feed.xml"
        fg.link(href=feed_url, rel='self', type='application/rss+xml')

        # Process each digest
        items_added = 0
        for digest in digests:
            try:
                entry = self._create_entry(fg, digest)
                if entry:
                    items_added += 1
            except Exception as e:
                print(f"Warning: Could not process {digest.path}: {e}")
                continue

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fg.rss_file(str(output_path), pretty=True)

        return items_added

    def _create_entry(self, fg: FeedGenerator, digest: DigestFile):
        """
        Create RSS entry from digest file.

        Args:
            fg: FeedGenerator instance
            digest: DigestFile to process

        Returns:
            FeedEntry instance or None if failed
        """
        # Load content
        markdown_content = digest.load_content()

        # Extract metadata
        title = self._extract_title(markdown_content)
        summary = self._extract_summary(markdown_content)

        # Convert markdown to HTML
        html_content = self._markdown_to_html(markdown_content)

        # Create entry
        fe = fg.add_entry()

        # Set required fields
        date_str = digest.date.strftime('%Y/%m/%d')
        filename = digest.path.name
        permalink = f"{self.base_url}/{date_str}/{filename}"
        guid = f"squid-digest-{digest.date.strftime('%Y-%m-%d')}"

        fe.id(guid)
        fe.title(title)
        fe.link(href=permalink)
        fe.description(summary)
        fe.content(html_content, type='html')

        # Make datetime timezone-aware (UTC)
        pub_date = digest.date.replace(hour=13, minute=0, second=0, tzinfo=timezone.utc)
        fe.published(pub_date)
        fe.updated(pub_date)

        # Add categories
        fe.category(term='trading-signals')
        fe.category(term='crypto')
        fe.category(term='ai-analysis')

        # Add author
        fe.author({'name': 'Squid Digest', 'email': 'squid@leviathannews.xyz'})

        return fe

    def _markdown_to_html(self, markdown_content: str) -> str:
        """
        Convert markdown to HTML.

        Uses GhostEmailClient.format_digest_html() if available,
        otherwise falls back to basic markdown2 conversion.

        Args:
            markdown_content: Markdown content

        Returns:
            HTML content
        """
        if self.ghost_client:
            try:
                return self.ghost_client.format_digest_html(markdown_content)
            except Exception as e:
                print(f"Warning: GhostEmailClient HTML conversion failed: {e}")
                print("Falling back to basic markdown conversion")

        # Fallback: basic markdown2 conversion
        try:
            import markdown2
            return markdown2.markdown(
                markdown_content,
                extras=['fenced-code-blocks', 'tables', 'header-ids']
            )
        except ImportError:
            # Last resort: return markdown as-is
            return f"<pre>{markdown_content}</pre>"

    def _extract_title(self, markdown_content: str) -> str:
        """
        Extract title from markdown H1.

        Args:
            markdown_content: Markdown content

        Returns:
            Title string (defaults to "Crypto Trading Signals" if not found)
        """
        # Pattern: # 📊 Crypto Trading Signals - November 29, 2025
        match = re.search(r'^#\s+(.+?)$', markdown_content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return "Crypto Trading Signals"

    def _extract_summary(self, markdown_content: str) -> str:
        """
        Generate short summary for RSS <description>.

        Extracts:
        - Market snapshot (BTC/ETH prices)
        - Number of trading signals
        - Backtest performance

        Args:
            markdown_content: Markdown content

        Returns:
            Summary string (~200-300 chars)
        """
        summary_parts = []

        # Extract BTC/ETH prices from Market Snapshot
        btc_match = re.search(r'\*\*\[?BTC\]?.*?\$([0-9,]+\.?[0-9]*?).*?\(([^)]+)\)', markdown_content)
        eth_match = re.search(r'\*\*\[?ETH\]?.*?\$([0-9,]+\.?[0-9]*?).*?\(([^)]+)\)', markdown_content)

        if btc_match and eth_match:
            summary_parts.append(f"Market: BTC ${btc_match.group(1)} ({btc_match.group(2)}), ETH ${eth_match.group(1)} ({eth_match.group(2)})")

        # Count trading signals (emoji indicators)
        signal_pattern = re.compile(r'🟢|🔴|🟡|🟠')
        signals = signal_pattern.findall(markdown_content)
        if signals:
            summary_parts.append(f"{len(signals)} trading signals")

        # Extract backtest returns
        buy_return_match = re.search(r'Buy.*?Strategy.*?Total Return:\s*\*?\*?([+-]?[0-9.]+%)', markdown_content, re.DOTALL | re.IGNORECASE)
        if buy_return_match:
            summary_parts.append(f"Buy Strategy: {buy_return_match.group(1)}")

        # Combine
        if summary_parts:
            return " | ".join(summary_parts)
        else:
            return "Daily crypto trading signals powered by AI analysis of Leviathan News"
