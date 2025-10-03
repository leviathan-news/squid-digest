"""Service for generating and publishing news digests."""

from typing import List, Dict, Any
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from squid_digest.tools import LeviathanNewsFetcher
from squid_digest.llm import OpenAIChatProvider, LLMChatProvider
from squid_digest.context.prompts.template import (
    DIGEST_PROMPT_TEMPLATE,
    SYSTEM_MESSAGE,
    DEFAULT_TAGS,
)


class DigestService:
    """
    Orchestrates the digest generation pipeline.

    Flow: Fetch news -> Generate AI digest -> Publish to Ghost
    """

    def __init__(
        self,
        new_fetcher: LeviathanNewsFetcher,
        llm_provider: LLMChatProvider,
        # ghost_client: GhostClient,
    ):
        """
        Initialize digest service with API clients.

        Args:
            new_fetcher: Client for fetching news
            llm_provider: Client for AI generation
            # ghost_client: Client for publishing
        """
        self.new_fetcher = new_fetcher
        self.llm_provider = llm_provider
        # self.ghost = ghost_client

    def fetch_news(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch news items from Leviathan News.

        Args:
            limit: Number of items to fetch

        Returns:
            List of news items
        """
        return self.new_fetcher.fetch_top_news(limit=limit)

    async def generate_writeup(self, news_items: List[Dict[str, Any]]) -> str:
        """
        Generate digest content using llm provider.

        Args:
            news_items: List of news items with headline, source, etc.

        Returns:
            Generated digest content, save to markdown file, in this repo
        """

        # prompt = DIGEST_PROMPT_TEMPLATE.format(headlines=headlines_text)
        chain = (
            SystemMessagePromptTemplate.from_template(SYSTEM_MESSAGE)
            | news_items
            | self.llm_provider
        )
        response = await chain.ainvoke({})
        return response.content

    def publish_writeup(self, digest_content: str) -> dict:
        """
        Publish digest to ...

        Args:
            digest_content: Generated digest text

        Returns:
            ...
        """
        pass

    def run_pipeline(self, limit: int = 10, dry_run: bool = True) -> str:
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
        digest_content = self.generate_writeup(news_items)

        # Step 3: Publish (unless dry run)
        if not dry_run:
            self.publish_writeup(digest_content)

        return digest_content
