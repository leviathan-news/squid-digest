import os
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

# Base LLM configuration
LLM_CHAT_PROVIDER = os.getenv("LLM_CHAT_PROVIDER", "deepseek")

# Individual provider configurations
OPENAI_CHAT_MODEL = {
    "API_KEY": os.getenv("OPENAI_API_KEY"),
    "MODEL": os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1"),
    "TEMPERATURE": float(os.getenv("OPENAI_TEMPERATURE", 0.7)),
    "MAX_TOKENS": int(os.getenv("OPENAI_MAX_TOKENS", 1000)),
}

# DeepSeek is the sole digest provider (2026-09-24). It was added as a
# fallback on 2026-07-16 after a Perplexity 401 left the digest dark
# 2026-07-02 → 07-15; the Perplexity key kept failing, so DeepSeek served
# every run from then on and Perplexity was removed. No web search —
# reasoning runs over the provided headlines only.
DEEPSEEK_CHAT_MODEL = {
    "API_KEY": os.getenv("DEEPSEEK_API_KEY"),
    "MODEL": os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-chat"),
    "BASE_URL": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    "TEMPERATURE": float(os.getenv("DEEPSEEK_TEMPERATURE", 0.7)),
    "MAX_TOKENS": int(os.getenv("DEEPSEEK_MAX_TOKENS", 4000)),
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
    elif LLM_CHAT_PROVIDER == "deepseek":
        return {
            "PROVIDER": "deepseek",
            "CHAT_MODEL": DEEPSEEK_CHAT_MODEL,
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
    import tempfile

    meta_path = get_meta_path(date)
    existing = load_meta(date)
    existing.update(data)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    # X delivery attempts must survive a crash without a half-written receipt.
    with tempfile.NamedTemporaryFile(mode='w', dir=meta_path.parent, delete=False) as handle:
        temporary = handle.name
        try:
            handle.write(json.dumps(existing, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            os.unlink(temporary)
            raise
    try:
        os.replace(temporary, meta_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


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


def truncate_at_word(text: str, limit: int) -> str:
    """Truncate *text* to at most *limit* chars without cutting a word in half.

    A blurb that ends mid-word ("...blockchain infrastructu") reads as
    broken, so we always cut at the last whitespace boundary that leaves
    room for a trailing single-char ellipsis (U+2026), stripping trailing
    punctuation first. Falls back to a hard cut only when no whitespace is
    available to cut on.
    """
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]

    budget = limit - 1  # reserve one char for the ellipsis
    window = text[:budget]
    cut = window.rfind(" ")
    if cut <= 0:
        return text[:limit]

    return window[:cut].rstrip(" ,;:-") + "…"


# Tier 2 template fallback budget for generate_blurb(); headlines are only
# included whole, so this bounds how many/how much of them fit.
TEMPLATE_BLURB_MAX_CHARS = 280


_BLURB_REFUSAL_PATTERNS = (
    "i cannot",
    "i'm unable",
    "i am unable",
    "i don't have",
    "search results provided",
    "cannot complete",
    "i apologize",
)


def _looks_like_refusal(blurb: str) -> bool:
    """True when an LLM response looks like a refusal or is unusably short."""
    if not blurb or len(blurb) < 20:
        return True
    lowered = blurb.lower()
    return any(p in lowered for p in _BLURB_REFUSAL_PATTERNS)


def generate_blurb(headlines: list, max_chars: int = 140) -> str:
    """Generate a human-sounding blurb from headlines via DeepSeek.

    Fallback chain:
    1. DeepSeek (short completion, 10s timeout)
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

    # --- Tier 1: DeepSeek ---
    # Was a direct Perplexity call; its key has returned 401 since July 2026,
    # so every blurb fell through to the template. The main digest already
    # runs on DeepSeek via the fallback in llm/providers.py.
    api_key = DEEPSEEK_CHAT_MODEL.get("API_KEY")
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
                f"{DEEPSEEK_CHAT_MODEL['BASE_URL']}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": DEEPSEEK_CHAT_MODEL["MODEL"],
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.7,
                },
                timeout=10,
            )
            resp.raise_for_status()
            blurb = resp.json()["choices"][0]["message"]["content"].strip()
            # Strip <think>...</think> tags and citation markers [1], [2]
            import re
            blurb = re.sub(r'<think>.*?</think>', '', blurb, flags=re.DOTALL).strip()
            blurb = re.sub(r'\[\d+\]', '', blurb).strip()
            if _looks_like_refusal(blurb):
                logger.warning(
                    "DeepSeek returned refusal or too-short blurb: %r. Falling through to template.",
                    blurb[:80],
                )
            elif blurb and len(blurb) <= max_chars:
                return blurb
            elif blurb:
                return truncate_at_word(blurb, max_chars)
        except Exception as e:
            logger.warning(f"DeepSeek blurb generation failed: {e}")

    # --- Tier 2: Smart template ---
    # Headlines are used whole or not at all — never sliced mid-word (the
    # old `h[:60]` here produced fragments like "job listings po"). Add
    # headlines in rank order while the fully rendered sentence still fits
    # the budget, stopping (not skipping ahead) at the first one that
    # doesn't fit.
    prefix = "In today's digest: "
    candidates = [h.strip().rstrip(".") for h in headlines[:3] if h and h.strip()]
    if candidates:
        accepted: list = []
        for h in candidates:
            trial = accepted + [h]
            if len(_render_digest_template(prefix, trial)) <= TEMPLATE_BLURB_MAX_CHARS:
                accepted = trial
            else:
                break
        if accepted:
            return _render_digest_template(prefix, accepted)
        # Even the top-ranked headline alone doesn't fit; cut it at a word
        # boundary rather than dropping it entirely.
        return prefix + truncate_at_word(candidates[0], TEMPLATE_BLURB_MAX_CHARS - len(prefix))

    # --- Tier 3: Default ---
    return DEFAULT_BLURB


def _render_digest_template(prefix: str, items: list) -> str:
    """Render the Tier 2 "In today's digest: ..." sentence for 1-3 items."""
    if len(items) == 1:
        return f"{prefix}{items[0]}"
    if len(items) == 2:
        return f"{prefix}{items[0]} and {items[1]}"
    return f"{prefix}{items[0]}, {items[1]}, and {items[2]}"
