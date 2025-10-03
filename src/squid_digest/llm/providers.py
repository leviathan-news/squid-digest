"""Classes for LLM chat providers."""

# import httpx
import os
from abc import ABC, abstractmethod
from typing import Optional, List
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from squid_digest.config import OPENAI_CHAT_MODEL


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


# class PerplexityProvider:
#     """Generates AI content using Perplexity API."""

#     API_URL = "https://api.perplexity.ai/chat/completions"
#     DEFAULT_MODEL = "sonar"

#     def __init__(self, api_key: str, timeout: int = 60):
#         self.api_key = api_key
#         self.timeout = timeout

#     def generate_completion(
#         self,
#         prompt: str,
#         system_message: str = "You are a helpful assistant.",
#         temperature: float = 0.7,
#         max_tokens: int = 1000,
#     ) -> str:
#         """
#         Generate AI completion from Perplexity.

#         Args:
#             prompt: User prompt to send
#             system_message: System message for context
#             temperature: Sampling temperature (0-1)
#             max_tokens: Maximum tokens in response

#         Returns:
#             Generated text content

#         Raises:
#             httpx.HTTPStatusError: If API request fails
#             KeyError: If response format is unexpected
#         """
#         headers = {
#             "Authorization": f"Bearer {self.api_key}",
#             "Content-Type": "application/json",
#         }

#         payload = {
#             "model": self.DEFAULT_MODEL,
#             "messages": [
#                 {"role": "system", "content": system_message},
#                 {"role": "user", "content": prompt},
#             ],
#             "stream": False,
#             "temperature": temperature,
#             "max_tokens": max_tokens,
#         }

#         with httpx.Client(timeout=self.timeout) as client:
#             response = client.post(self.API_URL, headers=headers, json=payload)
#             response.raise_for_status()
#             data = response.json()

#         return data["choices"][0]["message"]["content"]
