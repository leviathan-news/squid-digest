import os
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

# Base LLM configuration
LLM_CHAT_PROVIDER = os.getenv("LLM_CHAT_PROVIDER", "perplexity")

# Individual provider configurations
OPENAI_CHAT_MODEL = {
    "API_KEY": os.getenv("OPENAI_API_KEY"),
    "MODEL": os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1"),
    "TEMPERATURE": float(os.getenv("OPENAI_TEMPERATURE", 0.7)),
    "MAX_TOKENS": int(os.getenv("OPENAI_MAX_TOKENS", 1000)),
}

PERPLEXITY_CHAT_MODEL = {
    "API_KEY": os.getenv("PERPLEXITY_API_KEY"),
    "MODEL": os.getenv("PERPLEXITY_CHAT_MODEL", "sonar-reasoning-pro"),
    "TEMPERATURE": float(os.getenv("PERPLEXITY_TEMPERATURE", 0.7)),
    "MAX_TOKENS": int(os.getenv("PERPLEXITY_MAX_TOKENS", 4000)),
    "REASONING": os.getenv("PERPLEXITY_REASONING", "high"),
}

WRITEUP_DIR = Path("writeup")
WRITEUP_DIR.mkdir(exist_ok=True)

# Backtest configuration
BACKTEST_INITIAL_CAPITAL = 10000.0
BACKTEST_PORTFOLIO_STATE_FILE = WRITEUP_DIR / "portfolio_state.json"
BACKTEST_PORTFOLIO_STATE_FILE_BUY = WRITEUP_DIR / "portfolio_state_buy.json"
BACKTEST_PORTFOLIO_STATE_FILE_SELL = WRITEUP_DIR / "portfolio_state_sell.json"

# Sentiment-based portfolio configuration
SENTIMENT_STATE_FILE = WRITEUP_DIR / "sentiment_state.json"
SENTIMENT_PORTFOLIO_STATE_FILE = WRITEUP_DIR / "sentiment_portfolio_state.json"
SENTIMENT_PORTFOLIO_INVERSE_STATE_FILE = WRITEUP_DIR / "sentiment_portfolio_inverse_state.json"


def get_writeup_date_path(date: datetime = None) -> Path:
    """
    Get the date-based subdirectory path for writeup files.
    
    Structure: writeup/YYYY/MM/DD/
    
    Args:
        date: Date to use (defaults to today)
    
    Returns:
        Path to the date-specific writeup directory
    """
    if date is None:
        date = datetime.now()
    
    date_dir = WRITEUP_DIR / date.strftime("%Y") / date.strftime("%m") / date.strftime("%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    return date_dir


def get_writeup_file_path(filename: str, date: datetime = None) -> Path:
    """
    Get the full path to a writeup file in the date-based structure.
    
    Args:
        filename: Name of the file (e.g., "signals_2025-11-14.md")
        date: Date to use for directory structure (defaults to today)
    
    Returns:
        Full path to the file
    """
    return get_writeup_date_path(date) / filename


# Unified LLM configuration based on provider
def get_llm_config() -> Dict[str, Any]:
    """Get the appropriate LLM configuration based on the provider."""
    if LLM_CHAT_PROVIDER == "openai":
        return {
            "PROVIDER": "openai",
            "CHAT_MODEL": OPENAI_CHAT_MODEL,
        }
    elif LLM_CHAT_PROVIDER == "perplexity":
        return {
            "PROVIDER": "perplexity",
            "CHAT_MODEL": PERPLEXITY_CHAT_MODEL,
        }
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_CHAT_PROVIDER}")


# Create the unified configuration
LLM_CHAT_CONFIG = get_llm_config()
