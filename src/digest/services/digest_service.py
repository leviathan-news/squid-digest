"""Service for generating and publishing news digests."""
from typing import List, Dict, Any
from digest.clients import LeviathanNewsClient, PerplexityClient, GhostClient


class DigestService:
    """
    Orchestrates the digest generation pipeline.

    Flow: Fetch news -> Generate AI digest -> Publish to Ghost
    """

    DIGEST_PROMPT_TEMPLATE = """You are a crypto and tech news analyst creating a daily digest. Based on these top headlines from Leviathan News, create a compelling daily digest that:

1. **Summarizes the key themes** across all stories
2. **Explains the significance** of each major story in 2-3 sentences
3. **Identifies trends** and patterns in the news
4. **Provides context** about why these stories matter to crypto/tech audiences
5. **Writes in an engaging, newsletter-style tone** that's informative but accessible

Today's Top Headlines:
{headlines}

Format your response as a newsletter digest with:
- A compelling subject line
- Brief intro paragraph
- 3-4 main story summaries with analysis
- A closing section highlighting key trends
- Keep it concise but insightful (aim for 300-500 words total)

Make it engaging and valuable for crypto/tech professionals who want to stay informed but don't have time to read everything."""

    SYSTEM_MESSAGE = "You are an expert crypto and tech news analyst who creates engaging daily digests."

    DEFAULT_TAGS = ["digest", "crypto", "tech", "news"]

    def __init__(
        self,
        leviathan_client: LeviathanNewsClient,
        perplexity_client: PerplexityClient,
        ghost_client: GhostClient
    ):
        """
        Initialize digest service with API clients.

        Args:
            leviathan_client: Client for fetching news
            perplexity_client: Client for AI generation
            ghost_client: Client for publishing
        """
        self.leviathan = leviathan_client
        self.perplexity = perplexity_client
        self.ghost = ghost_client

    def fetch_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch news items from Leviathan News.

        Args:
            limit: Number of items to fetch

        Returns:
            List of news items
        """
        return self.leviathan.fetch_top_news(limit=limit)

    def generate_digest(self, news_items: List[Dict[str, Any]]) -> str:
        """
        Generate digest content using AI.

        Args:
            news_items: List of news items with headline, source, etc.

        Returns:
            Generated digest content
        """
        # Format headlines for the prompt
        headlines_text = "\n".join([
            f"• {item.get('headline', 'No headline')} (Source: {item.get('source', 'Unknown')})"
            for item in news_items
        ])

        prompt = self.DIGEST_PROMPT_TEMPLATE.format(headlines=headlines_text)

        return self.perplexity.generate_completion(
            prompt=prompt,
            system_message=self.SYSTEM_MESSAGE,
            temperature=0.7,
            max_tokens=1000
        )

    def publish_digest(self, digest_content: str) -> dict:
        """
        Publish digest to Ghost.

        Args:
            digest_content: Generated digest text

        Returns:
            Ghost API response
        """
        # Extract subject line (first line) and body (rest)
        lines = digest_content.strip().split('\n')
        title = lines[0] if lines else "Daily Crypto & Tech Digest"
        body = '\n'.join(lines[1:]) if len(lines) > 1 else digest_content

        return self.ghost.create_post(
            title=title,
            content=body,
            tags=self.DEFAULT_TAGS,
            status="published",
            meta_description="Daily digest of top crypto and tech news from Leviathan News"
        )

    def run_pipeline(self, limit: int = 10, dry_run: bool = False) -> str:
        """
        Run the full digest pipeline.

        Args:
            limit: Number of news items to process
            dry_run: If True, generate but don't publish

        Returns:
            Generated digest content

        Raises:
            Various exceptions from API clients
        """
        # Step 1: Fetch news
        news_items = self.fetch_news(limit=limit)

        if not news_items:
            raise ValueError("No news items fetched")

        # Step 2: Generate digest
        digest_content = self.generate_digest(news_items)

        # Step 3: Publish (unless dry run)
        if not dry_run:
            self.publish_digest(digest_content)

        return digest_content
