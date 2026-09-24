"""Classes for LLM chat providers."""

from abc import ABC, abstractmethod
from typing import Optional
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from squid_digest.config import (
    DEEPSEEK_CHAT_MODEL,
    OPENAI_CHAT_MODEL,
)


class LLMChatProvider(ABC):
    """Abstract base class for LLM chat providers."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def get_model(self, **kwargs) -> BaseChatModel:
        """Get LangChain chat model instance."""
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """Get default model name for this provider."""
        pass


class OpenAIChatProvider(LLMChatProvider):
    """OpenAI LLM chat provider."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(api_key, model)
        self.api_key = api_key or OPENAI_CHAT_MODEL["API_KEY"]

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

    def get_default_model(self) -> str:
        """Get default OpenAI model."""
        return OPENAI_CHAT_MODEL["MODEL"]

    def get_model(self, **kwargs) -> BaseChatModel:
        """Get OpenAI chat model instance."""
        return ChatOpenAI(
            model=self.model or self.get_default_model(), api_key=self.api_key, **kwargs
        )


class DeepSeekChatProvider(LLMChatProvider):
    """DeepSeek LLM chat provider (OpenAI-compatible endpoint).

    Sole digest provider since 2026-09-24. Perplexity was removed after its
    key returned 401 on every run from 2026-07-16; DeepSeek had been serving
    every digest through the fallback since then. No web search: the model
    reasons over the provided headlines only.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(api_key, model)
        self.api_key = api_key or DEEPSEEK_CHAT_MODEL["API_KEY"]

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is required")

    def get_default_model(self) -> str:
        """Get default DeepSeek model."""
        return DEEPSEEK_CHAT_MODEL["MODEL"]

    def get_model(self, prompt_type: str = "signals", **kwargs) -> BaseChatModel:
        """Get DeepSeek chat model instance.

        prompt_type is accepted for call-site compatibility (it named the
        Perplexity thinking logs) and is unused.
        """
        return ChatOpenAI(
            model=self.model or self.get_default_model(),
            api_key=self.api_key,
            base_url=DEEPSEEK_CHAT_MODEL["BASE_URL"],
            temperature=DEEPSEEK_CHAT_MODEL["TEMPERATURE"],
            max_tokens=DEEPSEEK_CHAT_MODEL["MAX_TOKENS"],
            **kwargs
        )
