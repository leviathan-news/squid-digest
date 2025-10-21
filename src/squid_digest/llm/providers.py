"""Classes for LLM chat providers."""

import httpx
import os
import re
from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime
from pathlib import Path
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

    def get_model(self, prompt_type: str = "signals", **kwargs) -> BaseChatModel:
        """Get Perplexity chat model instance."""
        # For now, we'll use a simple HTTP-based implementation
        # In the future, this could be replaced with a proper LangChain integration
        return PerplexityLangChainModel(
            model=self.model or self.get_default_model(),
            api_key=self.api_key,
            prompt_type=prompt_type,
            **kwargs
        )


class PerplexityLangChainModel(BaseChatModel):
    """Custom LangChain model for Perplexity API."""
    
    API_URL: str = "https://api.perplexity.ai/chat/completions"
    model: str
    api_key: str
    temperature: float = 0.7
    max_tokens: int = PERPLEXITY_CHAT_MODEL["MAX_TOKENS"]
    prompt_type: str = "signals"
    
    def __init__(self, model: str, api_key: str, temperature: float = 0.7, max_tokens: int = None, prompt_type: str = "signals", **kwargs):
        # Use config default if max_tokens not provided
        if max_tokens is None:
            max_tokens = PERPLEXITY_CHAT_MODEL["MAX_TOKENS"]
        super().__init__(model=model, api_key=api_key, temperature=temperature, max_tokens=max_tokens, prompt_type=prompt_type, **kwargs)
    
    def _extract_and_log_thinking(self, content: str, prompt_type: str = None) -> str:
        """
        Extract thinking content from <think> tags and save to log file.
        Returns cleaned content without thinking tags.
        """
        # Use instance prompt type if not provided
        if prompt_type is None:
            prompt_type = self.prompt_type
        
        # Create thinking logs directory
        thinking_logs_dir = Path("writeup/thinking_logs")
        thinking_logs_dir.mkdir(exist_ok=True)
        
        # Generate log filename
        today = datetime.now().strftime("%Y-%m-%d")
        log_filename = thinking_logs_dir / f"{prompt_type}_{today}_thinking.log"
        
        # Extract thinking content using regex
        # Pattern 1: <think>...</think> (closed tags)
        closed_pattern = r'<think>(.*?)</think>'
        closed_matches = re.findall(closed_pattern, content, re.DOTALL)
        
        # Pattern 2: <think>... (unclosed tag - everything after <think>)
        unclosed_pattern = r'<think>(.*)$'
        unclosed_match = re.search(unclosed_pattern, content, re.DOTALL)
        
        thinking_content = ""
        cleaned_content = content
        
        if closed_matches:
            # Handle closed tags
            thinking_content = "\n\n".join(closed_matches)
            cleaned_content = re.sub(closed_pattern, '', content, flags=re.DOTALL)
        elif unclosed_match:
            # Handle unclosed tag
            thinking_content = unclosed_match.group(1)
            cleaned_content = re.sub(unclosed_pattern, '', content, flags=re.DOTALL)
        
        # Save thinking content to log file if any was found
        if thinking_content.strip():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"\n{'='*60}\n[{timestamp}] Thinking Log for {prompt_type}\n{'='*60}\n{thinking_content.strip()}\n"
            
            with open(log_filename, "a", encoding="utf-8") as f:
                f.write(log_entry)
        
        # Clean up any remaining whitespace and return
        return cleaned_content.strip()

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
        user_content = ""
        
        for message in messages:
            if hasattr(message, 'content'):
                role = "system" if message.__class__.__name__ == "SystemMessage" else "user"
                api_messages.append({"role": role, "content": message.content})
                if role == "user":
                    user_content = message.content
        
        # Ensure last message is from user (Perplexity requirement)
        if api_messages and api_messages[-1]["role"] == "system":
            # Move system message to beginning and add a user message
            system_msg = api_messages[-1]
            # If no user content found, use a default prompt
            if not user_content:
                user_content = "Please analyze the provided crypto headlines and provide market insights."
            api_messages = [system_msg] + [{"role": "user", "content": user_content}]

        payload = {
            "model": self.model,
            "messages": api_messages,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        with httpx.Client(timeout=120) as client:
            response = client.post(self.API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        
        # Extract and log thinking content, return cleaned content
        cleaned_content = self._extract_and_log_thinking(content)
        
        # Return in LangChain format
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=cleaned_content))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        """Async generate response from Perplexity API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Convert LangChain messages to Perplexity format
        api_messages = []
        user_content = ""
        
        for message in messages:
            if hasattr(message, 'content'):
                role = "system" if message.__class__.__name__ == "SystemMessage" else "user"
                api_messages.append({"role": role, "content": message.content})
                if role == "user":
                    user_content = message.content
        
        # Ensure last message is from user (Perplexity requirement)
        if api_messages and api_messages[-1]["role"] == "system":
            # Move system message to beginning and add a user message
            system_msg = api_messages[-1]
            # If no user content found, use a default prompt
            if not user_content:
                user_content = "Please analyze the provided crypto headlines and provide market insights."
            api_messages = [system_msg] + [{"role": "user", "content": user_content}]

        payload = {
            "model": self.model,
            "messages": api_messages,
            "stream": False,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(self.API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        
        # Extract and log thinking content, return cleaned content
        cleaned_content = self._extract_and_log_thinking(content)
        
        # Return in LangChain format
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=cleaned_content))])
