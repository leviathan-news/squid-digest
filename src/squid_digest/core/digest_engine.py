"""Service for generating and publishing news digests."""

from typing import List, Dict, Any
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from dotenv import load_dotenv

from langfuse.langchain import CallbackHandler
from squid_digest.tools import LeviathanNewsFetcher
from squid_digest.llm import OpenAIChatProvider, LLMChatProvider
from squid_digest.context.prompts.template import SYSTEM_MESSAGE

load_dotenv()

langfuse_handler = CallbackHandler()


class DigestEngine:
    """
    Orchestrates the digest generation pipeline.

    Flow: Fetch news -> Generate AI digest -> Publish to Ghost
    """

    def __init__(
        self,
        news_fetcher: LeviathanNewsFetcher,
        llm_chat_provider: LLMChatProvider,
        # ghost_client: GhostClient,
    ):
        """
        Initialize digest service with API clients.

        Args:
            new_fetcher: Client for fetching news
            llm_provider: Client for AI generation
            # ghost_client: Client for publishing
        """
        self.news_fetcher = news_fetcher
        self.llm_chat_provider = llm_chat_provider
        # self.ghost = ghost_client

    async def generate_writeup(self, text):
        """
        Generate digest content using llm provider.

        Args:
            news_items: List of news items with headline, source, etc.

        Returns:
            Generated digest content, save to markdown file, in this repo
        """
        prompt = SYSTEM_MESSAGE.format(headlines=text)

        # Create a simple chain with the formatted prompt
        prompt_template = ChatPromptTemplate.from_messages([("system", prompt)])
        chain = prompt_template | self.llm_chat_provider.get_model()
        response = await chain.ainvoke({}, callbacks=[langfuse_handler])
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
