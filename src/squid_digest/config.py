import os
from typing import Dict, Any
from pathlib import Path

# Base LLM configuration
LLM_CHAT_PROVIDER = os.getenv("LLM_CHAT_PROVIDER", "openai")

# Individual provider configurations
OPENAI_CHAT_MODEL = {
    "API_KEY": os.getenv("OPENAI_API_KEY"),
    "MODEL": os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1"),
    "TEMPERATURE": float(os.getenv("OPENAI_TEMPERATURE", 0.7)),
    "MAX_TOKENS": int(os.getenv("OPENAI_MAX_TOKENS", 1000)),
}

WRITEUP_DIR = Path("writeup")
WRITEUP_DIR.mkdir(exist_ok=True)


# Unified LLM configuration based on provider
def get_llm_config() -> Dict[str, Any]:
    """Get the appropriate LLM configuration based on the provider."""
    if LLM_CHAT_PROVIDER == "openai":
        return {
            "PROVIDER": "openai",
            "CHAT_MODEL": OPENAI_CHAT_MODEL,
        }

    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_CHAT_PROVIDER}")


# Create the unified configuration
LLM_CHAT_CONFIG = get_llm_config()
