"""Client for Perplexity AI API."""
import httpx
from typing import List, Dict, Any


class PerplexityClient:
    """Generates AI content using Perplexity API."""

    API_URL = "https://api.perplexity.ai/chat/completions"
    DEFAULT_MODEL = "sonar"

    def __init__(self, api_key: str, timeout: int = 60):
        self.api_key = api_key
        self.timeout = timeout

    def generate_completion(
        self,
        prompt: str,
        system_message: str = "You are a helpful assistant.",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Generate AI completion from Perplexity.

        Args:
            prompt: User prompt to send
            system_message: System message for context
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response

        Returns:
            Generated text content

        Raises:
            httpx.HTTPStatusError: If API request fails
            KeyError: If response format is unexpected
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]
