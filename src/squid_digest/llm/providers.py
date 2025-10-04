"""Classes for LLM chat providers."""

import httpx
import os
from abc import ABC, abstractmethod
from typing import Optional, List
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from squid_digest.config import OPENAI_CHAT_MODEL, PERPLEXITY_CHAT_MODEL


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


class PerplexityChatProvider(LLMChatProvider):
    """Perplexity LLM chat provider."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        super().__init__(api_key, model)
        self.api_key = api_key or PERPLEXITY_CHAT_MODEL["API_KEY"]

        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY environment variable is required")

    def get_default_model(self) -> str:
        """Get default Perplexity model."""
        return PERPLEXITY_CHAT_MODEL["MODEL"]

    def get_model(self, **kwargs) -> BaseChatModel:
        """Get Perplexity chat model instance."""
        # For now, we'll use a simple HTTP-based implementation
        # In the future, this could be replaced with a proper LangChain integration
        return PerplexityLangChainModel(
            model=self.model or self.get_default_model(),
            api_key=self.api_key,
            **kwargs
        )


class PerplexityLangChainModel(BaseChatModel):
    """Custom LangChain model for Perplexity API."""
    
    API_URL: str = "https://api.perplexity.ai/chat/completions"
    model: str
    api_key: str
    temperature: float = 0.7
    max_tokens: int = 1000
    
    def __init__(self, model: str, api_key: str, temperature: float = 0.7, max_tokens: int = 1000, **kwargs):
        super().__init__(model=model, api_key=api_key, temperature=temperature, max_tokens=max_tokens, **kwargs)

    @property
    def _llm_type(self) -> str:
        return "perplexity"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """Generate response from Perplexity API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Convert LangChain messages to Perplexity format
        api_messages = []
        for message in messages:
            if hasattr(message, 'content'):
                role = "system" if message.__class__.__name__ == "SystemMessage" else "user"
                api_messages.append({"role": role, "content": message.content})
        
        # Ensure last message is from user (Perplexity requirement)
        if api_messages and api_messages[-1]["role"] == "system":
            # Move system message to beginning and add a user message
            system_msg = api_messages[-1]
            api_messages = [system_msg] + [{"role": "user", "content": "Please analyze the provided content."}]

        payload = {
            "model": self.model,
            "messages": api_messages,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        with httpx.Client(timeout=60) as client:
            response = client.post(self.API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        
        # Return in LangChain format
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        """Async generate response from Perplexity API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Convert LangChain messages to Perplexity format
        api_messages = []
        for message in messages:
            if hasattr(message, 'content'):
                role = "system" if message.__class__.__name__ == "SystemMessage" else "user"
                api_messages.append({"role": role, "content": message.content})
        
        # Ensure last message is from user (Perplexity requirement)
        if api_messages and api_messages[-1]["role"] == "system":
            # Move system message to beginning and add a user message
            system_msg = api_messages[-1]
            api_messages = [system_msg] + [{"role": "user", "content": "Please analyze the provided content."}]

        payload = {
            "model": self.model,
            "messages": api_messages,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self.API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        
        # Return in LangChain format
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
