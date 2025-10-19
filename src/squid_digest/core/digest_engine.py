"""Service for generating and publishing news digests."""

from typing import List, Dict, Any
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from dotenv import load_dotenv

from squid_digest.tools import LeviathanNewsFetcher
from squid_digest.llm import OpenAIChatProvider, PerplexityChatProvider, LLMChatProvider
from squid_digest.context.prompts.template import SYSTEM_MESSAGE, ACTIVE_PROMPT

load_dotenv()

# Make langfuse optional
try:
    from langfuse.langchain import CallbackHandler
    langfuse_handler = CallbackHandler()
except ImportError:
    langfuse_handler = None


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

    async def generate_writeup_with_prompt(self, headlines: str, token_list: str = "", system_message: str = None, prompt_type: str = "signals"):
        """
        Generate trading signals using custom system message and prompt type.

        Args:
            headlines: Formatted string of news headlines with URLs
            token_list: Formatted string of tracked tokens
            system_message: Custom system message to use
            prompt_type: Type of prompt for thinking logs

        Returns:
            Generated trading signals content
        """
        if system_message is None:
            system_message = SYSTEM_MESSAGE
        
        prompt = system_message.format(headlines=headlines, token_list=token_list)

        # Create a simple chain with the formatted prompt
        prompt_template = ChatPromptTemplate.from_messages([("system", prompt)])
        chain = prompt_template | self.llm_chat_provider.get_model(prompt_type=prompt_type)
        response = await chain.ainvoke({}, callbacks=[langfuse_handler] if langfuse_handler else [])
        return response.content

    async def generate_writeup(self, headlines: str, token_list: str = ""):
        """
        Generate trading signals using llm provider.

        Args:
            headlines: Formatted string of news headlines with URLs
            token_list: Formatted string of tracked tokens

        Returns:
            Generated trading signals content
        """
        prompt = SYSTEM_MESSAGE.format(headlines=headlines, token_list=token_list)

        # Create a simple chain with the formatted prompt
        prompt_template = ChatPromptTemplate.from_messages([("system", prompt)])
        chain = prompt_template | self.llm_chat_provider.get_model(prompt_type=ACTIVE_PROMPT)
        response = await chain.ainvoke({}, callbacks=[langfuse_handler] if langfuse_handler else [])
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
