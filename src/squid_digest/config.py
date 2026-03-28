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


# --- Distribution URL helpers (single source of truth) ---

TELEGRAM_CHANNEL_INVITE = "https://t.me/+8A2-Ypry6ytjYTYx"
DEFAULT_BLURB = "Daily crypto trading signals from Leviathan News"
SQUID_DIGEST_IMAGE_URL = "https://digest.leviathannews.xyz/content/images/2025/09/Digest-2.jpg"


def get_digest_title(date: datetime) -> str:
    """Shared title for Ghost posts — used by draft creation, publish, and updates."""
    return f"\U0001f991 Leviathan News Daily Digest - {date.strftime('%B %d, %Y')}"


def get_canonical_url(date: datetime) -> str:
    """Generate deterministic canonical URL for digest on Ghost CMS.

    This is a best-guess based on the slug pattern Ghost uses.
    Prefer ``resolve_digest_url()`` which checks the meta JSON for
    the actual published Ghost URL first.
    """
    month = date.strftime("%B").lower()
    day = date.day
    year = date.year
    return f"https://digest.leviathannews.xyz/leviathan-news-daily-digest-{month}-{day}-{year}/"


def get_github_url(date: datetime) -> str:
    """Generate GitHub URL for digest markdown file."""
    return (
        f"https://github.com/leviathan-news/squid-digest/blob/main/writeup/"
        f"{date.year}/{date.month:02d}/{date.day:02d}/signals_{date.strftime('%Y-%m-%d')}.md"
    )


def get_meta_path(date: datetime) -> Path:
    """Return the path to the per-date metadata JSON file."""
    return get_writeup_date_path(date) / f"meta_{date.strftime('%Y-%m-%d')}.json"


def load_meta(date: datetime) -> dict:
    """Load the per-date metadata JSON, returning ``{}`` if missing."""
    import json

    meta_path = get_meta_path(date)
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_meta(date: datetime, data: dict) -> None:
    """Merge *data* into the per-date metadata JSON and write it back."""
    import json

    meta_path = get_meta_path(date)
    existing = load_meta(date)
    existing.update(data)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(existing, indent=2) + "\n")


def resolve_digest_url(date: datetime) -> str:
    """Return the best available digest URL for *date*.

    May include draft URLs — suitable for internal channels (Telegram planning, Cave).
    For public distribution (𝕏, broadcast), use ``resolve_public_digest_url()``.
    """
    meta = load_meta(date)
    return (
        meta.get("published_ghost_url")
        or meta.get("draft_ghost_url")
        or meta.get("ghost_url")  # legacy key
        or get_canonical_url(date)
    )


def resolve_public_digest_url(date: datetime) -> str:
    """Return a published-only digest URL for *date*.

    Never returns draft URLs. Safe for public distribution (𝕏, broadcast channel).
    Falls back to the deterministic canonical URL.
    """
    meta = load_meta(date)
    return meta.get("published_ghost_url") or get_canonical_url(date)


def generate_blurb(headlines: list, max_chars: int = 200) -> str:
    """Generate a human-sounding blurb from headlines via Perplexity.

    Fallback chain:
    1. Perplexity AI (short completion, 10s timeout)
    2. Smart template ("In today's digest: h1, h2, and h3")
    3. DEFAULT_BLURB constant

    Args:
        headlines: List of headline strings (top 3-5).
        max_chars: Max blurb length.
    """
    import logging
    logger = logging.getLogger(__name__)

    if not headlines:
        return DEFAULT_BLURB

    # --- Tier 1: Perplexity AI ---
    api_key = PERPLEXITY_CHAT_MODEL.get("API_KEY")
    if api_key:
        try:
            import httpx

            prompt = (
                f"Summarize these crypto news headlines into one engaging sentence "
                f"(under {max_chars} characters) for a social media teaser. "
                f"Mention token names and key numbers. No hashtags, no emojis.\n\n"
                + "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines[:5]))
            )

            resp = httpx.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.7,
                },
                timeout=10,
            )
            resp.raise_for_status()
            blurb = resp.json()["choices"][0]["message"]["content"].strip()
            # Strip any <think>...</think> tags from reasoning models
            import re
            blurb = re.sub(r'<think>.*?</think>', '', blurb, flags=re.DOTALL).strip()
            if blurb and len(blurb) <= max_chars:
                return blurb
            elif blurb:
                return blurb[:max_chars - 3] + "..."
        except Exception as e:
            logger.warning(f"Perplexity blurb generation failed: {e}")

    # --- Tier 2: Smart template ---
    short = [h[:60] for h in headlines[:3]]
    if len(short) >= 3:
        return f"In today's digest: {short[0]}, {short[1]}, and {short[2]}"
    elif len(short) == 2:
        return f"In today's digest: {short[0]} and {short[1]}"
    elif short:
        return f"In today's digest: {short[0]}"

    # --- Tier 3: Default ---
    return DEFAULT_BLURB
