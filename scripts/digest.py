"""
Script for generating writeup for each news content or bundle all news content
"""

import asyncio, json, argparse, random
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import httpx

load_dotenv()
from squid_digest.tools.leviathan import LeviathanNewsFetcher
from squid_digest.core.digest_engine import DigestEngine
from squid_digest.llm import PerplexityChatProvider
from squid_digest.config import (
    WRITEUP_DIR, BACKTEST_INITIAL_CAPITAL, BACKTEST_PORTFOLIO_STATE_FILE,
    BACKTEST_PORTFOLIO_STATE_FILE_BUY, BACKTEST_PORTFOLIO_STATE_FILE_SELL,
    SENTIMENT_STATE_FILE, SENTIMENT_PORTFOLIO_STATE_FILE,
    SENTIMENT_PORTFOLIO_INVERSE_STATE_FILE,
    get_writeup_file_path, save_meta, DEFAULT_BLURB,
)
import os
from squid_digest.context.prompts.template import ACTIVE_PROMPT as DEFAULT_ACTIVE_PROMPT, get_fallback_system_message
from squid_digest.backtest.incremental_backtest import IncrementalBacktest
from squid_digest.backtest.newsletter_formatter import format_backtest_for_newsletter
from squid_digest.backtest.signal_parser import SignalParser
from squid_digest.backtest.price_fetcher import PriceFetcher
from squid_digest.backtest.sentiment_state import SentimentTracker
from squid_digest.backtest.sentiment_portfolio import SentimentPortfolio, format_sentiment_portfolio_results, format_dual_sentiment_portfolios

# Allow ACTIVE_PROMPT to be overridden by environment variable
ACTIVE_PROMPT = os.getenv('ACTIVE_PROMPT', DEFAULT_ACTIVE_PROMPT)
import logging

logger = logging.getLogger(__name__)

# Synonyms for "moron" - randomly selected for disclaimer variety (~130 unique terms)
MORON_SYNONYMS = [
    "moron", "idiot", "fool", "imbecile", "dunce", "simpleton", "nincompoop", "dolt",
    "blockhead", "numbskull", "dimwit", "halfwit", "nitwit", "dullard", "dope", "dork",
    "knucklehead", "bonehead", "meathead", "lunkhead", "thickhead", "pinhead", "airhead", "birdbrain",
    "pea-brain", "scatterbrain", "chowderhead", "muttonhead", "lamebrain", "dumbass", "dummy", "dum-dum",
    "dumb-bell", "dumb-bunny", "dumb-cluck", "dumb-ox", "ignoramus", "clod", "clodpole", "clodpate",
    "clodpoll", "clodhopper", "clodhead", "oaf", "boob", "chump", "sap",
    "saphead", "schmuck", "putz", "klutz", "dweeb", "goof", "goofball", "doofus",
    "dingbat", "ding-dong", "ding-a-ling", "dipstick", "dip", "ditz", "ditzel", "bozo",
    "buffoon", "clown", "jester", "joker", "zany", "wacko", "wacky", "crackpot",
    "crank", "nut", "nutcase", "nutjob", "screwball", "weirdo", "oddball", "kook",
    "kooky", "loon", "loony", "lunatic", "maniac", "psycho",  
    "madman", "cuckoo", "wackadoodle",
    "numpty", "muppet", "plonker", "pillock", "berk", "prat", "twit", "tosser",
    "git", "galoot", "galumph", "gawk", "gawky", "gormless", "lummox", "lubber",
    "lout", "yahoo", "yokel", "rube", "hick", "hayseed", "bumpkin", "dunderhead", 
    "loggerhead", "mooncalf", "addlepate", "addlehead"
]


def proxy_image_url_for_github(url: str) -> str:
    """
    Proxy image URL through a public image proxy service for GitHub markdown compatibility.
    
    GitHub's markdown renderer sometimes blocks external images from certain domains.
    Using a public image proxy ensures images display correctly in GitHub markdown.
    
    Args:
        url: Original image URL
        
    Returns:
        Proxied image URL that works with GitHub markdown
    """
    if not url:
        return url
    
    # Use images.weserv.nl as a free public image proxy
    # This service proxies images and makes them accessible to GitHub
    from urllib.parse import quote
    encoded_url = quote(url, safe='')
    return f"https://images.weserv.nl/?url={encoded_url}"


def generate_squid_pass_winner_section(winner_data):
    """
    Generate a featured SQUID Pass winner section.
    
    Args:
        winner_data: Dictionary containing squid_pass_winner data from API
        
    Returns:
        Formatted HTML string for the featured SQUID Pass winner section, or empty string if no winner
    """
    if not winner_data or not winner_data.get("squid_pass_winner"):
        return ""
    
    winner = winner_data["squid_pass_winner"]
    
    # Extract winner data
    headline = winner.get('headline', 'No headline')
    source = winner.get('source', 'Unknown source')
    url = winner.get('url', '#')
    media_url = winner.get('media', '')
    tags = winner.get('tags', [])
    top_yaps = winner.get('top_yaps', [])
    news_id = winner.get('id', '')
    canonical_url = winner.get('canonical_url', f"https://leviathannews.xyz/news/{news_id}")
    
    # Format tags (top 3) - just emoji and tag names
    tag_links = []
    for tag in tags[:3]:
        tag_name = tag.get('name', '')
        tag_id = tag.get('id', '')
        tag_slug = tag.get('slug', '')
        if tag_name and tag_id and tag_slug:
            tag_links.append(f'<a href="https://leviathannews.xyz/t/{tag_id}/{tag_slug}">{tag_name}</a>')
    
    tags_str = " • ".join(tag_links) if tag_links else ""
    
    # Get top comment if available
    top_comment = ""
    if top_yaps:
        top_yap = top_yaps[0]  # Highest scored comment
        comment_text = top_yap.get('text', '')
        comment_author = top_yap.get('author', {}).get('display_name', 'Anonymous')
        if comment_text:
            # Link commenter username to their profile comments page with UTM codes
            comment_author_link = f"https://leviathannews.xyz/u/{comment_author}/comments?utm_medium=digest&utm_source=digest&utm_campaign=comments"
            top_comment = f"💬 <i>{comment_text}</i> — <a href=\"{comment_author_link}\">@{comment_author}</a>"
    
    # Return just the table row (will be part of Top Stories table)
    # Style the row with orange background (border will be on table wrapper)
    section = "  <tr style=\"background-color: #FFF5F2;\">\n"
    
    # Image cell - make images 50% wider (525px)
    section += "    <td style=\"width: 525px; min-width: 525px; vertical-align: center; padding: 16px 12px 16px 16px;\">\n"
    if media_url:
        # Use proxied URL for GitHub markdown compatibility
        proxied_url = proxy_image_url_for_github(media_url)
        section += f"      <img src=\"{proxied_url}\" alt=\"SQUID Pass Winner\" width=\"525\" style=\"min-width: 525px; max-width: 100%; height: auto; border-radius: 4px;\">\n"
    section += "    </td>\n"
    
    # Content cell - use same vertical-align as Top Stories
    section += "    <td style=\"vertical-align: center; padding: 16px;\">\n"
    section += f"      <h3 style=\"margin-top: 0; color: #FF6B35;\">🏆 SQUID Pass Winner</h3>\n"
    # Remove headline hyperlink, only link source (redirect URL with UTM codes)
    redirect_url = f"https://leviathannews.xyz/redirect/{news_id}?utm_medium=digest&utm_source=digest&utm_campaign=news&skip_landing=true"
    section += f"      {headline} - <a href=\"{redirect_url}\"><strong>{source}</strong></a>\n"

    if tags_str:
        section += f"      <br><span style=\"font-size: 0.9em;\">🏷️ {tags_str}</span>\n"

    if top_comment:
        section += f"      <br><blockquote style=\"margin: 8px 0; padding: 8px 12px; border-left: 3px solid #999; background-color: #f5f5f5; font-style: italic;\">{top_comment}</blockquote>\n"
    
    section += "    </td>\n"
    section += "  </tr>\n"
    
    return section


def generate_top_stories_section(news_data, limit=5, squid_pass_winner_data=None):
    """
    Generate a formatted top stories section from Leviathan News data.

    Args:
        news_data: List of news items from Leviathan API
        limit: Number of top stories to include
        squid_pass_winner_data: Optional SQUID Pass winner data to insert after story 5

    Returns:
        Formatted markdown string for the top stories section
    """
    top_stories = news_data[:limit]

    section = "## 🔥 Top Stories\n\n"
    # Use vertical layout (image on top, text below) for better Ghost compatibility
    section += "<div style=\"border: 2px solid #FF6B35; border-radius: 8px; overflow: hidden;\">\n"

    for i, story in enumerate(top_stories, 1):
        # Extract story data
        headline = story.get('headline', 'No headline')
        source = story.get('source', 'Unknown source')
        url = story.get('url', '#')
        media_url = story.get('media', '')
        tags = story.get('tags', [])
        top_yaps = story.get('top_yaps', [])
        
        # Format tags (top 3) - just emoji and tag names
        tag_links = []
        for tag in tags[:3]:
            tag_name = tag.get('name', '')
            tag_id = tag.get('id', '')
            tag_slug = tag.get('slug', '')
            if tag_name and tag_id and tag_slug:
                tag_links.append(f'<a href="https://leviathannews.xyz/t/{tag_id}/{tag_slug}">{tag_name}</a>')
        
        tags_str = " • ".join(tag_links) if tag_links else ""
        
        # Get top comment if available
        top_comment = ""
        if top_yaps:
            top_yap = top_yaps[0]  # Highest scored comment
            comment_text = top_yap.get('text', '')
            comment_author = top_yap.get('author', {}).get('display_name', 'Anonymous')
            if comment_text:
                # Link commenter username to their profile comments page with UTM codes
                comment_author_link = f"https://leviathannews.xyz/u/{comment_author}/comments?utm_medium=digest&utm_source=digest&utm_campaign=comments"
                top_comment = f"💬 <i>{comment_text}</i> — <a href=\"{comment_author_link}\">@{comment_author}</a>"
        
        # Format as vertical div (image on top, text below) for Ghost compatibility
        section += "  <div style=\"padding: 16px; border-bottom: 1px solid #e0e0e0;\">\n"
        
        # Image on top
        if media_url:
            # Use proxied URL for GitHub markdown compatibility
            proxied_url = proxy_image_url_for_github(media_url)
            section += f"    <img src=\"{proxied_url}\" alt=\"Story Image\" style=\"width: 100%; max-width: 100%; height: auto; border-radius: 4px; margin-bottom: 12px;\">\n"
        
        # Content below image
        # Remove headline hyperlink, only link source (redirect URL with UTM codes)
        news_id = story.get('id', '')
        redirect_url = f"https://leviathannews.xyz/redirect/{news_id}?utm_medium=digest&utm_source=digest&utm_campaign=news&skip_landing=true"
        section += f"    <p style=\"margin: 0 0 8px 0;\">{i}. {headline} - <a href=\"{redirect_url}\"><strong>{source}</strong></a></p>\n"

        if tags_str:
            section += f"    <p style=\"margin: 0 0 8px 0; font-size: 0.9em;\">🏷️ {tags_str}</p>\n"

        if top_comment:
            section += f"    <blockquote style=\"margin: 8px 0; padding: 8px 12px; border-left: 3px solid #999; background-color: #f5f5f5; font-style: italic;\">{top_comment}</blockquote>\n"

        section += "  </div>\n"

    # Insert SQUID Pass Winner after story 5 (if available)
    if squid_pass_winner_data and squid_pass_winner_data.get('squid_pass_winner'):
        winner = squid_pass_winner_data.get('squid_pass_winner', {})
        headline = winner.get('headline', 'No headline')
        source = winner.get('source', 'Unknown source')
        media_url = winner.get('media', '')
        tags = winner.get('tags', [])
        top_yaps = winner.get('top_yaps', [])
        news_id = winner.get('id', '')

        # Format tags
        tag_links = []
        for tag in tags[:3]:
            tag_name = tag.get('name', '')
            tag_id = tag.get('id', '')
            tag_slug = tag.get('slug', '')
            if tag_name and tag_id and tag_slug:
                tag_links.append(f'<a href="https://leviathannews.xyz/t/{tag_id}/{tag_slug}">{tag_name}</a>')

        tags_str = " • ".join(tag_links) if tag_links else ""

        # Get top comment
        top_comment = ""
        if top_yaps:
            top_yap = top_yaps[0]
            comment_text = top_yap.get('text', '')
            comment_author = top_yap.get('author', {}).get('display_name', 'Anonymous')
            if comment_text:
                comment_author_link = f"https://leviathannews.xyz/u/{comment_author}/comments?utm_medium=digest&utm_source=digest&utm_campaign=comments"
                top_comment = f"💬 <i>{comment_text}</i> — <a href=\"{comment_author_link}\">@{comment_author}</a>"

        # Add SQUID Pass Winner with orange background (vertical layout)
        section += "  <div style=\"padding: 16px; background-color: #FFF5F2;\">\n"
        
        # Image on top
        if media_url:
            proxied_url = proxy_image_url_for_github(media_url)
            section += f"    <img src=\"{proxied_url}\" alt=\"SQUID Pass Winner\" style=\"width: 100%; max-width: 100%; height: auto; border-radius: 4px; margin-bottom: 12px;\">\n"

        # Content below image
        section += f"    <h3 style=\"margin-top: 0; color: #FF6B35;\">🏆 SQUID Pass Winner</h3>\n"
        redirect_url = f"https://leviathannews.xyz/redirect/{news_id}?utm_medium=digest&utm_source=digest&utm_campaign=news&skip_landing=true"
        section += f"    <p style=\"margin: 0 0 8px 0;\">{headline} - <a href=\"{redirect_url}\"><strong>{source}</strong></a></p>\n"

        if tags_str:
            section += f"    <p style=\"margin: 0 0 8px 0; font-size: 0.9em;\">🏷️ {tags_str}</p>\n"

        if top_comment:
            section += f"    <blockquote style=\"margin: 8px 0; padding: 8px 12px; border-left: 3px solid #999; background-color: #f5f5f5; font-style: italic;\">{top_comment}</blockquote>\n"

        section += "  </div>\n"

    section += "</div>\n"

    return section


# Tokens the Leviathan API doesn't flag as stablecoins but should be
# (uppercased to match symbol normalization below)
STABLECOIN_OVERRIDES = {'BUIDL', 'FDUSD', 'USDM', 'USDTB', 'USR', 'SDAI'}


def _is_token_map_schema_current(token_id_map: dict) -> bool:
    """Check if a cached token map has the current schema (canonical_tag + stablecoin)."""
    if not token_id_map:
        return False
    # Spot-check the first entry for required keys
    sample = next(iter(token_id_map.values()), {})
    return 'canonical_tag' in sample and 'stablecoin' in sample


def _get_token_id_map():
    """
    Get a mapping of token symbols to Leviathan canonical tags.
    Caches the result to avoid repeated API calls.
    Uses canonical_tag instead of id for proper URL generation.
    """
    cache_file = Path(".data/leviathan_token_id_map.json")
    cached_map = {}

    # Try to load from cache first
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                cached_map = json.load(f)
        except Exception:
            pass

    # If cache is current schema, use it directly
    if _is_token_map_schema_current(cached_map):
        return cached_map

    # Cache is missing or stale schema — try to refresh from API
    try:
        leviathan_fetcher = LeviathanNewsFetcher()
        token_data = leviathan_fetcher.fetch_tokens(save=False)
        token_id_map = {}

        for token in token_data.get('tokens', []):
            symbol = token.get('symbol', '').strip('$').upper()
            canonical_tag = token.get('canonical_tag')
            token_name = token.get('name', '')

            if symbol and canonical_tag:
                token_id_map[symbol] = {
                    'canonical_tag': canonical_tag,
                    'name': token_name,
                    'stablecoin': token.get('stablecoin', False),
                }

        # Apply stablecoin overrides for tokens the API doesn't flag
        for sym in STABLECOIN_OVERRIDES:
            if sym in token_id_map:
                token_id_map[sym]['stablecoin'] = True

        # Save to cache
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump(token_id_map, f)

        return token_id_map
    except Exception as e:
        logger.warning(f"Could not fetch token IDs: {e}")
        # Fall back to stale cache if available (degraded: no stablecoin
        # filtering, but canonical_tag/name may still work for links)
        if cached_map:
            logger.warning("Using stale token ID cache as fallback")
            return cached_map
        return {}


def transform_trading_signals_markdown(trading_signals_text: str) -> str:
    """
    Transform trading signals from AI format to new markdown format.
    
    Transforms from: **$BTC Bitcoin: STRONG BUY** - reason
    To: 🟢 Bitcoin (<a href="https://leviathannews.xyz/t/171/BTC?utm_medium=digest&utm_source=digest&utm_campaign=trading_signals">$BTC</a>): STRONG BUY - reason
    
    Args:
        trading_signals_text: Raw trading signals markdown from AI
        
    Returns:
        Transformed trading signals markdown
    """
    import re
    
    # Get token ID mapping
    token_id_map = _get_token_id_map()
    
    # Signal type to emoji mapping
    signal_emoji_map = {
        'STRONG BUY': '🟢',
        'BUY': '🟢',
        'WEAK BUY': '🟡',
        'WEAK SELL': '🟠',
        'SELL': '🔴',
        'STRONG SELL': '🔴'
    }
    
    # Pattern to match: **$SYMBOL Token Name: SIGNAL** - reason ([more info](URL))
    # Capture reason but exclude the ([more info](URL)) part
    signal_pattern = re.compile(
        r'\*\*\$([A-Za-z0-9]+)\s+([^:]+?):\s+([A-Z\s]+)\*\*\s*-\s*(.+?)(?:\s*\(\[more info\]\([^)]+\)\))?\s*$',
        re.MULTILINE | re.DOTALL
    )
    
    def transform_signal(match):
        symbol = match.group(1).upper()
        token_name = match.group(2).strip()
        signal_type = match.group(3).strip()
        reason = match.group(4).strip()
        
        # Remove the ([more info](URL)) part from reason if present
        # This handles cases where it might still be captured
        reason = re.sub(r'\s*\(\[more info\]\([^)]+\)\)\s*$', '', reason, flags=re.MULTILINE).strip()

        # Strip Perplexity citation markers like [1], [2]
        reason = re.sub(r'\[\d+\]', '', reason).strip()

        # Get emoji for signal type
        emoji = signal_emoji_map.get(signal_type, '⚪')
        
        # Get token canonical_tag for link
        token_info = token_id_map.get(symbol, {})
        canonical_tag = token_info.get('canonical_tag')
        token_name_from_map = token_info.get('name', token_name)
        
        # Use token name from map if available, otherwise use parsed name
        display_name = token_name_from_map if token_name_from_map else token_name
        
        # Create link if we have canonical_tag
        if canonical_tag:
            link = f"https://leviathannews.xyz/t/{canonical_tag}/{symbol}?utm_medium=digest&utm_source=digest&utm_campaign=trading_signals"
            symbol_link = f'<a href="{link}">${symbol}</a>'
        else:
            symbol_link = f'${symbol}'
        
        # Format as: EMOJI Token Name ($SYMBOL link): SIGNAL - reason
        return f'{emoji} {display_name} ({symbol_link}): {signal_type} - {reason}'
    
    # Transform all signals - preserve line structure
    # Split by lines first to maintain structure
    lines = trading_signals_text.split('\n')
    transformed_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        # Check if this line contains a signal pattern
        if signal_pattern.search(line_stripped):
            # Transform this line
            transformed_line = signal_pattern.sub(transform_signal, line_stripped)
            transformed_lines.append(transformed_line)
        elif line_stripped:
            # Keep non-signal lines as-is
            transformed_lines.append(line_stripped)
        else:
            # Preserve empty lines
            transformed_lines.append('')
    
    # Join with newlines, then ensure double line breaks between signals
    transformed = '\n'.join(transformed_lines)
    
    # Ensure signals are separated by double line breaks
    # Replace single newlines between signals with double newlines
    import re
    # Pattern: signal line (starts with emoji) followed by another signal line
    transformed = re.sub(
        r'([🟢🔴🟡🟠⚪][^\n]+)\n([🟢🔴🟡🟠⚪])',
        r'\1\n\n\2',
        transformed
    )
    
    return transformed


def _coerce_hold_like_signal_type(reason: str) -> str:
    """Coerce HOLD/NEUTRAL-like outputs into WEAK BUY/WEAK SELL as last resort.

    This is only used when the LLM outputs disallowed labels (e.g., HOLD/NEUTRAL),
    which would otherwise break downstream parsing/backtesting and fail the run.
    """
    reason_lower = (reason or "").lower()

    bearish_keywords = [
        "exploit", "hack", "drain", "vulnerability", "breach", "lawsuit", "ban",
        "investigation", "charges", "risk", "concern", "downgrade", "outage",
        "bearish", "headwind", "liquidat", "sell-off", "scam",
    ]
    bullish_keywords = [
        "upgrade", "launch", "partnership", "adoption", "growth", "integrat",
        "approval", "win", "expand", "bullish", "tailwind", "support",
    ]

    if any(k in reason_lower for k in bearish_keywords):
        return "WEAK SELL"
    if any(k in reason_lower for k in bullish_keywords):
        return "WEAK BUY"
    # Default to the least opinionated "action" label (still valid for pipeline).
    return "WEAK BUY"


def canonicalize_trading_signals_to_bold_lines(trading_signals_text: str) -> str:
    """Convert common non-standard LLM outputs into the expected bold-per-line format.

    The backtest parser is most reliable when signals look like:
    **$SYMBOL Token Name: SIGNAL TYPE** - reason ([more info](URL))
    """
    import re

    if not trading_signals_text:
        return trading_signals_text

    # If the model already produced bold $SYMBOL lines, keep as-is.
    if re.search(r'^\s*(?:[-*]\s*)?\*\*\$[A-Za-z0-9]+', trading_signals_text, flags=re.MULTILINE):
        return trading_signals_text

    signal_emojis = {'🟢', '🔴', '🟡', '🟠', '⚪'}
    dash_separators = [' - ', ' — ', ' – ', ' -', ' —', ' –']

    def extract_url(text: str) -> str | None:
        # Prefer explicit markdown link URL, else any http(s) URL.
        m = re.search(r'\(\s*https?://[^)\s]+\s*\)', text)
        if m:
            return m.group(0).strip('()').strip()
        m = re.search(r'https?://[^\s)]+', text)
        return m.group(0) if m else None

    out_lines: list[str] = []
    for raw_line in trading_signals_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('#'):
            continue
        if line.startswith('```') or line.startswith('---'):
            continue

        # Strip bullet/list prefix.
        line = re.sub(r'^\s*[-*]\s+', '', line)

        url = extract_url(line)

        # Find symbol ($XYZ preferred).
        sym_match = re.search(r'\$([A-Za-z0-9]{2,12})', line)
        symbol = sym_match.group(1).upper() if sym_match else None

        # Emoji-only symbol formats like: 🟢 BTC: Buy signal - reason
        if symbol is None and line and line[0] in signal_emojis:
            m = re.match(r'^[🟢🔴🟡🟠⚪]\s*([A-Za-z0-9]{2,12})\b', line)
            if m:
                symbol = m.group(1).upper()

        if symbol is None:
            # As a last resort, pick the first ALLCAPS token-like word if we see a buy/sell-ish keyword.
            if re.search(r'\b(buy|sell|hold|neutral|short|long)\b', line, re.IGNORECASE):
                m = re.search(r'\b([A-Z]{2,12})\b', line)
                if m:
                    symbol = m.group(1).upper()

        if symbol is None:
            continue

        # Detect signal type from explicit labels or keywords.
        explicit_label = None
        for candidate in SignalParser.VALID_SIGNALS:
            pattern = r'\b' + re.escape(candidate).replace(r'\ ', r'\s+') + r'\b'
            if re.search(pattern, line, re.IGNORECASE):
                explicit_label = candidate
                break

        if explicit_label:
            signal_type = explicit_label
        else:
            # Try keywords around ':' / '-' separators.
            after = line
            # Prefer substring after ':' if present.
            if ':' in after:
                after = after.split(':', 1)[1]
            signal_type = SignalParser.normalize_signal_type(after) or SignalParser.normalize_signal_type(line)

        if signal_type is None:
            # If we can’t classify it, skip; better than creating junk trades.
            continue

        # Extract a token name if present (e.g., "Bitcoin ($BTC)" or "Bitcoin - $BTC").
        token_name = None
        name_match = re.search(rf'([A-Za-z][A-Za-z0-9 .&/-]{{2,}})\s*\(\s*\${symbol}\s*\)', line)
        if name_match:
            token_name = name_match.group(1).strip()
        if token_name is None and line and line[0] in signal_emojis:
            # Emoji line, take leading words before '(' or ':' as name.
            name_part = re.sub(r'^[🟢🔴🟡🟠⚪]\s*', '', line)
            name_part = name_part.split('(', 1)[0].split(':', 1)[0].strip()
            # Avoid using the symbol itself as a "name".
            if name_part and name_part.upper() != symbol:
                token_name = name_part
        if token_name is None:
            token_name = symbol

        # Extract reason: prefer content after a dash separator; else after the signal label keyword.
        reason = ""
        for sep in dash_separators:
            if sep in line:
                reason = line.split(sep, 1)[1].strip()
                break
        if not reason:
            # Fallback: use everything after ':' as "reason", stripping obvious label words.
            reason = line.split(':', 1)[1].strip() if ':' in line else line
            # Remove leading signal-ish words.
            reason = re.sub(r'^(strong\s+)?(buy|sell|weak\s+buy|weak\s+sell|hold|neutral)\b[:\-\s]*', '', reason, flags=re.IGNORECASE).strip()

        # Remove any embedded URLs from the reason (we append as more info below).
        reason = re.sub(r'https?://[^\s)]+', '', reason).strip()
        if not reason:
            reason = "News-driven catalyst noted in today’s headlines"

        out = f"**${symbol} {token_name}: {signal_type}** - {reason}"
        if url:
            out += f" ([more info]({url}))"
        out_lines.append(out)

    return "\n".join(out_lines) if out_lines else trading_signals_text


def coerce_trading_signals_to_supported_types(
    trading_signals_text: str,
    *,
    allow_hold_coercion: bool,
) -> tuple[str, list[dict]]:
    """Normalize signal type labels to supported values used by parsing/backtests.

    This keeps the original tokens/reasons, but rewrites the signal label to one of:
    STRONG BUY, BUY, WEAK BUY, WEAK SELL, SELL, STRONG SELL.
    """
    import re

    if not trading_signals_text:
        return trading_signals_text, []

    changes: list[dict] = []
    out_lines: list[str] = []

    # Expected base format (from prompts): **$SYMBOL Token Name: SIGNAL** - reason ...
    # We only rewrite lines that already look like signals in this form.
    line_re = re.compile(
        r'^\s*\*\*\$([A-Za-z0-9]+)\s+([^:]+?):\s+([^*]+?)\*\*\s*-\s*(.+?)\s*$',
        re.IGNORECASE
    )

    for raw_line in trading_signals_text.splitlines():
        line = raw_line.strip()
        m = line_re.match(line)
        if not m:
            out_lines.append(raw_line)
            continue

        symbol = m.group(1).upper()
        token_name = m.group(2).strip()
        raw_signal_type = m.group(3).strip()
        reason = m.group(4).strip()

        normalized = SignalParser.normalize_signal_type(raw_signal_type)
        if normalized is None and allow_hold_coercion:
            holdish = raw_signal_type.upper()
            if any(word in holdish for word in ["HOLD", "NEUTRAL", "WAIT", "WATCH", "NO TRADE", "NO-TRADE"]):
                normalized = _coerce_hold_like_signal_type(reason)

        if normalized and raw_signal_type.strip() != normalized:
            changes.append({
                "symbol": symbol,
                "from": raw_signal_type,
                "to": normalized,
            })
            out_lines.append(f"**${symbol} {token_name}: {normalized}** - {reason}")
        else:
            out_lines.append(raw_line)

    return "\n".join(out_lines), changes


def validate_signals_against_whitelist(
    trading_signals_text: str,
    valid_symbols: set,
    stablecoin_symbols: set,
) -> tuple:
    """Validate signal lines against the daily token universe.

    Removes:
    - Signals for tokens not in valid_symbols (hallucinated tokens like $65, $PPI)
    - Signals for stablecoins (even if in valid_symbols)
    - Duplicate signals for the same token (keeps first occurrence)
    - Citation markers [1], [2], etc. from all lines

    Args:
        trading_signals_text: Canonicalized bold-format signal text.
        valid_symbols: Uppercase symbols from today's merged token universe.
        stablecoin_symbols: Uppercase symbols that are stablecoins.

    Returns:
        (cleaned_text, list of rejection dicts for logging)
    """
    import re

    if not trading_signals_text:
        return trading_signals_text, []

    line_re = re.compile(
        r'^\s*\*\*\$([A-Za-z0-9]+)\s+[^:]+?:\s+[^*]+?\*\*\s*-\s*.+',
        re.IGNORECASE,
    )

    seen_symbols = set()
    rejections = []
    out_lines = []

    for raw_line in trading_signals_text.splitlines():
        m = line_re.match(raw_line.strip())
        if not m:
            # Non-signal line — strip citations and keep
            out_lines.append(re.sub(r'\[\d+\]', '', raw_line))
            continue

        symbol = m.group(1).upper()

        if symbol in stablecoin_symbols:
            rejections.append({'symbol': symbol, 'reason': 'stablecoin'})
            continue

        if symbol not in valid_symbols:
            rejections.append({'symbol': symbol, 'reason': 'not_in_whitelist'})
            continue

        if symbol in seen_symbols:
            rejections.append({'symbol': symbol, 'reason': 'duplicate'})
            continue

        seen_symbols.add(symbol)
        # Strip citation markers like [1], [2] from the signal line
        out_lines.append(re.sub(r'\[\d+\]', '', raw_line).strip())

    return '\n'.join(out_lines), rejections


def generate_market_snapshot(verbose=False):
    """
    Generate a market snapshot with BTC, ETH, OPEN prices and notable movers.

    Args:
        verbose: Whether to print verbose logging

    Returns:
        Formatted markdown string for market snapshot section
        
    Raises:
        ValueError: If COINGECKO_API_KEY is not set (required for reliable market data)
    """
    import time
    import os
    
    # Get CoinGecko API key from environment - REQUIRED for reliable market data
    coingecko_api_key = os.getenv("COINGECKO_API_KEY")
    if not coingecko_api_key:
        error_msg = (
            "COINGECKO_API_KEY is required but not set. "
            "Set it in GitHub secrets (COINGECKO_API_KEY) or environment variables. "
            "Without it, market snapshot generation will fail due to rate limits."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    if verbose:
        logger.info("Using CoinGecko API key for rate limit avoidance")
    
    def fetch_with_retry(url, params, max_retries=3, retry_delay=2):
        """Fetch with retry logic for rate limiting."""
        client = None
        try:
            # Prepare headers with API key if available
            headers = {}
            if coingecko_api_key:
                headers['x-cg-demo-api-key'] = coingecko_api_key
            
            client = httpx.Client(timeout=30.0)
            for attempt in range(max_retries):
                try:
                    response = client.get(url, params=params, headers=headers)
                    if response.status_code == 429:
                        # Rate limited - wait and retry
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        if verbose:
                            logger.warning(f"Rate limited (429), waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        if verbose:
                            logger.warning(f"Rate limited (429), waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                        time.sleep(wait_time)
                        continue
                    raise
            return None
        finally:
            if client:
                client.close()
    
    try:
        # Get token ID mapping for Leviathan links
        token_id_map = _get_token_id_map()
        
        # Get BTC, ETH, OPEN prices with 24h change
        major_coins_url = "https://api.coingecko.com/api/v3/simple/price"
        major_params = {
            "ids": "bitcoin,ethereum,open-stablecoin-index",
            "vs_currencies": "usd",
            "include_24hr_change": "true"
        }

        major_prices = fetch_with_retry(major_coins_url, major_params)
        if not major_prices:
            raise Exception("Failed to fetch major coin prices after retries")

        # Format major coin prices
        btc_price = major_prices.get("bitcoin", {}).get("usd", 0)
        btc_change = major_prices.get("bitcoin", {}).get("usd_24h_change", 0)
        eth_price = major_prices.get("ethereum", {}).get("usd", 0)
        eth_change = major_prices.get("ethereum", {}).get("usd_24h_change", 0)
        open_price = major_prices.get("open-stablecoin-index", {}).get("usd", 0)
        open_change = major_prices.get("open-stablecoin-index", {}).get("usd_24h_change", 0)

        if verbose:
            logger.info(f"BTC: ${btc_price:,.2f} ({btc_change:+.2f}%)")
            logger.info(f"ETH: ${eth_price:,.2f} ({eth_change:+.2f}%)")
            logger.info(f"OPEN: ${open_price:.4f} ({open_change:+.2f}%)")

        # Format major coins as bullet points with links
        def format_major_coin(symbol, price, change, use_comma=True):
            sign = "+" if change >= 0 else ""
            emoji = "🟢" if change >= 0 else "🔴"
            if use_comma:
                price_str = f"${price:,.2f}"
            else:
                price_str = f"${price:.4f}"
            
            # Get token canonical_tag for link
            token_info = token_id_map.get(symbol, {})
            canonical_tag = token_info.get('canonical_tag')
            
            if canonical_tag:
                link = f"https://leviathannews.xyz/t/{canonical_tag}/{symbol}?utm_medium=digest&utm_source=digest&utm_campaign=market_snapshot"
                return f"• {emoji} **[{symbol}]({link})**: {price_str} ({sign}{change:.2f}%)"
            else:
                return f"• {emoji} **{symbol}**: {price_str} ({sign}{change:.2f}%)"

        major_coins = [
            format_major_coin("BTC", btc_price, btc_change),
            format_major_coin("ETH", eth_price, eth_change),
            format_major_coin("OPEN", open_price, open_change, use_comma=False)
        ]

        # Get notable movers from tracked tokens
        price_fetcher = PriceFetcher()
        token_mapping = price_fetcher._load_token_mapping()

        # Fetch prices for all tracked tokens (limit to top 50 by market cap/volume)
        # Get unique coingecko IDs
        coingecko_ids = list(set([slug for slug in token_mapping.values() if slug]))[:50]

        # Fetch in batches (CoinGecko has limits)
        all_movers = []
        batch_size = 50
        client = httpx.Client(timeout=30.0)
        try:
            for i in range(0, len(coingecko_ids), batch_size):
                batch = coingecko_ids[i:i+batch_size]
                batch_params = {
                    "ids": ",".join(batch),
                    "vs_currencies": "usd",
                    "include_24hr_change": "true"
                }

                try:
                    # Add delay between batches to avoid rate limiting
                    if i > 0:
                        time.sleep(1)  # 1 second delay between batches
                    
                    batch_prices = fetch_with_retry(major_coins_url, batch_params)
                    if not batch_prices:
                        if verbose:
                            logger.warning(f"Could not fetch prices for batch {i//batch_size + 1}")
                        continue

                    for coin_id, data in batch_prices.items():
                        change_24h = data.get("usd_24h_change", 0)
                        if change_24h and abs(change_24h) > 0.1:  # Only include meaningful changes
                            # Find symbol from mapping
                            symbol = next((sym for sym, cg_id in token_mapping.items() if cg_id == coin_id), coin_id.upper())
                            price = data.get("usd", 0)
                            all_movers.append({
                                "symbol": symbol.upper() if len(symbol) <= 6 else coin_id.upper(),
                                "change": change_24h,
                                "price": price
                            })
                except Exception as e:
                    if verbose:
                        logger.warning(f"Could not fetch prices for batch: {e}")
                    continue
        finally:
            client.close()

        # Sort and get top/bottom movers
        all_movers.sort(key=lambda x: x["change"], reverse=True)
        top_gainers = all_movers[:3]
        top_losers = all_movers[-3:][::-1]  # Reverse to show worst first

        # Format gainers as bullet points with links
        def format_mover(mover, is_gainer=True):
            symbol = mover['symbol']
            change = mover['change']
            sign = "+" if change >= 0 else ""
            emoji = "🟢" if is_gainer else "🔴"
            price = mover.get('price', 0)
            
            # Format price - use comma for prices >= 1000, otherwise no comma
            if price >= 1000:
                price_str = f"${price:,.2f}"
            elif price >= 1:
                price_str = f"${price:.2f}"
            else:
                price_str = f"${price:.4f}"
            
            # Get token canonical_tag for link
            token_info = token_id_map.get(symbol, {})
            canonical_tag = token_info.get('canonical_tag')
            
            if canonical_tag:
                link = f"https://leviathannews.xyz/t/{canonical_tag}/{symbol}?utm_medium=digest&utm_source=digest&utm_campaign=market_snapshot"
                return f"• {emoji} **[{symbol}]({link})**: {price_str} ({sign}{change:.1f}%)"
            else:
                return f"• {emoji} **{symbol}**: {price_str} ({sign}{change:.1f}%)"

        gainers_lines = [format_mover(g, is_gainer=True) for g in top_gainers] if top_gainers else ["• No significant gainers"]
        losers_lines = [format_mover(l, is_gainer=False) for l in top_losers] if top_losers else ["• No significant losers"]

        price_fetcher.close()

        # Build section with bullet point formatting
        section = f"""## 💰 Market Snapshot (24h)
{chr(10).join(major_coins)}

**📈 Top Gainers:**
{chr(10).join(gainers_lines)}

**📉 Top Losers:**
{chr(10).join(losers_lines)}
"""
        return section

    except Exception as e:
        logger.error(f"Error generating market snapshot: {e}")
        # Return minimal section if API fails
        return "## 💰 Market Snapshot (24h)\n\n*Market data temporarily unavailable*\n\n"


def fetch_news(limit=5, verbose=False, resolve_urls=False):
    if verbose:
        logger.info(f"Starting news fetch process (limit: {limit})")
        logger.info(f"Creating/using data directory: {Path('.data').absolute()}")
    
    leviathan_news_fetcher = LeviathanNewsFetcher()
    news = leviathan_news_fetcher.fetch_news(limit=limit)
    
    if verbose:
        logger.info(f"✓ Fetched {len(news)} news items")
        logger.info(f"✓ Created/updated: .data/leviathan_news.json")
    
    # Only resolve redirect URLs if requested (slow operation)
    if resolve_urls:
        news_with_redirect_url = leviathan_news_fetcher.get_redirect_url(news)
        if verbose:
            logger.info(f"✓ Processed redirect URLs for {len(news_with_redirect_url)} items")
            logger.info(f"✓ Created/updated: .data/leviathan_news_redirect_url.json")
    else:
        if verbose:
            logger.info("✓ Skipping URL resolution (use --resolve-urls if needed)")
    
    if verbose:
        logger.info("✓ Skipping content scraping - Perplexity will handle this")
        logger.info("News fetch process completed successfully")
    
    return news


def fetch_tokens(verbose=False):
    """Fetch token list from Leviathan News API."""
    if verbose:
        logger.info("Starting token fetch process")
        logger.info(f"Creating/using data directory: {Path('.data').absolute()}")
    
    leviathan_news_fetcher = LeviathanNewsFetcher()
    token_data = leviathan_news_fetcher.fetch_tokens()
    
    if verbose:
        logger.info(f"✓ Fetched {token_data['count']} tokens across {token_data['total_pages']} pages")
        logger.info(f"✓ Created/updated: .data/leviathan_tokens.json")
        logger.info("Token fetch process completed successfully")
    
    return token_data


async def each_news_content(limit=5, verbose=False):
    """
    Generate writeup for each news content

    Args:
        limit: Just to be safe in case the file has lot of news
        verbose: Enable verbose logging
    """
    if verbose:
        logger.info(f"Starting individual writeup generation (limit: {limit})")
        logger.info(f"Creating/using writeup directory: {WRITEUP_DIR.absolute()}")
    
    engine = DigestEngine(
        news_fetcher=LeviathanNewsFetcher(),
        llm_chat_provider=PerplexityChatProvider(),
    )
    
    data_file = Path(".data/leviathan_news_content.json")
    if verbose:
        logger.info(f"Reading news content from: {data_file.absolute()}")
    
    with open(data_file, "r") as f:
        news_content = json.load(f)
    
    if verbose:
        logger.info(f"Found {len(news_content)} news items, processing first {min(limit, len(news_content))}")
    
    for i, content in enumerate(news_content[:limit]):
        if verbose:
            logger.info(f"Generating writeup for news item {i+1}/{min(limit, len(news_content))} (ID: {content['id']})")
        
        response_content = await engine.generate_writeup(
            headlines=content["content"],
            token_list=""
        )  # TODO: add title, description to promt
        
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        filename = get_writeup_file_path(f"writeup_{today_str}_id_{content['id']}.md", today)
        
        if verbose:
            logger.info(f"Writing writeup to: {filename.absolute()}")
        
        with open(filename, "w") as f:
            f.write(response_content)
        
        if verbose:
            logger.info(f"✓ Created: {filename}")
    
    if verbose:
        logger.info("Individual writeup generation completed successfully")


async def bundle_writeup(verbose=False):
    if verbose:
        logger.info("Starting trading signals generation")
        logger.info(f"Creating/using writeup directory: {WRITEUP_DIR.absolute()}")
    
    engine = DigestEngine(
        news_fetcher=LeviathanNewsFetcher(),
        llm_chat_provider=PerplexityChatProvider(),
    )
    
    # Read the raw news data
    # Note: This reads from the cached file which may only have top 10 items
    # For comprehensive token extraction, we should fetch all news from past 24h
    data_file = Path(".data/leviathan_news.json")
    if verbose:
        logger.info(f"Reading news data from: {data_file.absolute()}")
    
    with open(data_file, "r") as f:
        news_data = json.load(f)
    
    # Also fetch ALL news from past 24h to ensure we catch long-tail tokens
    # This ensures tokens mentioned in stories beyond the top 10 are included
    if verbose:
        logger.info("Fetching all news from past 24 hours for comprehensive token extraction...")
    try:
        all_news_24h = engine.news_fetcher.fetch_all_news_24h(save=False)
        if verbose:
            logger.info(f"✓ Found {len(all_news_24h)} total news items from past 24h")
        # Use all news for token extraction, but keep original news_data for top stories
        news_data_for_tokens = all_news_24h
    except Exception as e:
        logger.warning(f"Could not fetch all news from 24h: {e}. Using cached news data only.")
        news_data_for_tokens = news_data
    
    # Read the token data
    token_file = Path(".data/leviathan_tokens.json")
    if not token_file.exists():
        if verbose:
            logger.info("Token data not found, fetching now...")
        fetch_tokens(verbose=verbose)
    
    if verbose:
        logger.info(f"Reading token data from: {token_file.absolute()}")
    
    with open(token_file, "r") as f:
        token_data = json.load(f)
    
    # Read the resolved redirect URLs (if they exist)
    redirect_file = Path(".data/leviathan_news_redirect_url.json")
    redirect_map = {}
    
    if redirect_file.exists():
        if verbose:
            logger.info(f"Reading redirect URLs from: {redirect_file.absolute()}")
        
        with open(redirect_file, "r") as f:
            redirect_data = json.load(f)
        
        # Create a mapping of news ID to resolved URL (clean HTML entities)
        import html
        redirect_map = {item["id"]: html.unescape(item["redirect_url"]) for item in redirect_data}
    else:
        if verbose:
            logger.info("No redirect URLs found - using original URLs (use --resolve-urls if needed)")
    
    if verbose:
        logger.info(f"Found {len(news_data)} news items")
        logger.info(f"Found {token_data['count']} tracked tokens")
    
    # Fetch SQUID Pass winner
    squid_pass_winner_data = None
    try:
        if verbose:
            logger.info("Fetching SQUID Pass winner...")
        squid_pass_winner_data = engine.news_fetcher.fetch_squid_pass_winner()
        if squid_pass_winner_data:
            if verbose:
                logger.info("✓ Found SQUID Pass winner")
        else:
            if verbose:
                logger.info("No SQUID Pass winner found (continuing without featured section)")
    except Exception as e:
        logger.warning(f"Error fetching SQUID Pass winner: {e}. Continuing without featured section.")
    
    # Generate the top stories section (which includes SQUID Pass Winner after story 5)
    top_stories_section = generate_top_stories_section(news_data, limit=5, squid_pass_winner_data=squid_pass_winner_data)

    # squid_pass_section is now included in top_stories_section, so we can set it to empty
    squid_pass_section = ""
    
    # Extract tokens from ALL news items' tags (to catch long-tail tokens)
    # This ensures tokens mentioned in stories beyond the top 10 are included
    # EXCLUDE stablecoins - we don't trade on stablecoin news
    tokens_from_news = {}
    stablecoins_filtered = 0
    for story in news_data_for_tokens:
        tags = story.get('tags', [])
        for tag in tags:
            if tag.get('is_token_tag') and tag.get('token'):
                token_info = tag['token']
                # Skip stablecoins - we don't trade on stablecoin news
                if token_info.get('stablecoin', False):
                    stablecoins_filtered += 1
                    continue
                token_symbol = token_info.get('symbol', '')
                if token_symbol:
                    # Store token info, preferring the most recent/complete data
                    if token_symbol not in tokens_from_news:
                        tokens_from_news[token_symbol] = token_info
    
    # Create a combined token set: API tokens + tokens found in today's news
    # Build a lookup by symbol for API tokens, EXCLUDING stablecoins
    api_tokens_by_symbol = {
        token.get('symbol', ''): token 
        for token in token_data['tokens'] 
        if not token.get('stablecoin', False)  # Exclude stablecoins
    }
    
    # Merge: start with API tokens (already filtered for stablecoins), then add/update with tokens from news
    all_relevant_tokens = {}
    for symbol, token in api_tokens_by_symbol.items():
        all_relevant_tokens[symbol] = token
    
    # Add tokens from news (these may not be in API or may have updated info)
    # Note: tokens_from_news already excludes stablecoins
    for symbol, token_info in tokens_from_news.items():
        # Double-check stablecoin status (should already be filtered, but be safe)
        if token_info.get('stablecoin', False):
            continue
        if symbol in all_relevant_tokens:
            # Update with news data (may have more recent info)
            all_relevant_tokens[symbol].update(token_info)
        else:
            # New token found in news but not in API
            all_relevant_tokens[symbol] = token_info
    
    # Format token list for the prompt
    # Prioritize: 1) tokens found in today's news, 2) then by news_count, 3) then by TVL
    def token_sort_key(token_tuple):
        symbol, token = token_tuple
        in_today_news = symbol in tokens_from_news
        news_count = token.get('news_count', 0)
        tvl = token.get('total_tvl', 0)
        # Sort: today's news tokens first, then by news_count, then TVL
        return (not in_today_news, -news_count, -tvl)
    
    sorted_tokens = sorted(all_relevant_tokens.items(), key=token_sort_key)
    
    # Include top 50 by priority, but ensure all tokens from today's news are included
    tokens_to_include = []
    tokens_from_news_included = set()
    
    # First, add all tokens found in today's news
    for symbol, token in sorted_tokens:
        if symbol in tokens_from_news:
            tokens_to_include.append((symbol, token))
            tokens_from_news_included.add(symbol)
    
    # Then add top tokens from API (up to 50 total, but prioritize today's news)
    for symbol, token in sorted_tokens:
        if len(tokens_to_include) >= 50 and symbol not in tokens_from_news_included:
            break
        if symbol not in tokens_from_news_included:
            tokens_to_include.append((symbol, token))
    
    token_list_str = "\n".join([
        f"{symbol} {token.get('name', 'Unknown')} - {token.get('news_count', 0)} news articles (TVL: ${token.get('total_tvl', 0):,.0f})"
        for symbol, token in tokens_to_include
    ])
    
    if verbose:
        logger.info("Generating trading signals...")
        logger.info(f"Token extraction summary:")
        logger.info(f"  - Tokens found in today's news: {len(tokens_from_news)}")
        logger.info(f"  - Stablecoins filtered out: {stablecoins_filtered}")
        logger.info(f"  - Total tokens to include: {len(tokens_to_include)}")
        logger.info(f"  - Tokens from news (long-tail): {', '.join(sorted(tokens_from_news.keys())[:10])}...")
    
    # Create a summary of headlines for the AI to analyze (use 10 for more context)
    # Use resolved URLs instead of tracking URLs
    headlines_summary = "\n".join([
        f"[{i+1}] {story.get('headline', 'No headline')} - {redirect_map.get(story.get('id'), story.get('url', 'No URL'))}"
        for i, story in enumerate(news_data[:10])
    ])
    
    # Generate trading signals
    if verbose:
        logger.info("Token list being sent to AI:")
        logger.info(f"Top 10 tokens: {', '.join([symbol for symbol, token in sorted_tokens[:10]])}")
        logger.info("Headlines being sent to AI:")
        logger.info(headlines_summary)
    
    trading_signals = await engine.generate_writeup(headlines=headlines_summary, token_list=token_list_str)

    # Prepare date and filename variables for error reporting
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    filename = get_writeup_file_path(f"{ACTIVE_PROMPT}_{today_str}.md", today)

    # VALIDATION: Check that LLM response is not empty or suspiciously short
    if not trading_signals or len(trading_signals.strip()) < 50:
        error_msg = (
            f"CRITICAL: LLM generated empty or suspiciously short response ({len(trading_signals.strip()) if trading_signals else 0} chars). "
            f"This indicates a potential API error or generation failure.\n"
            f"Response content: {trading_signals[:500] if trading_signals else '(empty)'}"
        )
        logger.error(error_msg)

        # Save diagnostic file for debugging
        diagnostic_file = filename.parent / f"diagnostic_{today_str}.txt"
        try:
            with open(diagnostic_file, "w") as f:
                f.write(f"Signal Generation Failure Diagnostic\n")
                f.write(f"=====================================\n\n")
                f.write(f"Error: {error_msg}\n\n")
                f.write(f"News items sent ({len(news_data)}):\n")
                f.write(f"{headlines_summary}\n\n")
                f.write(f"Token list sent ({len(tokens_to_include)} tokens):\n")
                f.write(f"{token_list_str[:500]}...\n\n")
                f.write(f"LLM Response:\n")
                f.write(f"{trading_signals}\n")
            logger.error(f"Diagnostic file saved to: {diagnostic_file}")
        except Exception as diag_error:
            logger.error(f"Could not save diagnostic file: {diag_error}")

        raise ValueError(error_msg)

    # Canonicalize + normalize signal labels early so parsing/backtesting is robust.
    trading_signals = canonicalize_trading_signals_to_bold_lines(trading_signals)
    trading_signals, coercion_changes = coerce_trading_signals_to_supported_types(
        trading_signals,
        allow_hold_coercion=False,
    )
    if coercion_changes:
        logger.warning(f"⚠️ Normalized {len(coercion_changes)} signal label(s) to supported types")

    # VALIDATION: Reject hallucinated tokens, stablecoins, duplicates; strip citations
    valid_symbols = {sym.strip('$').upper() for sym in all_relevant_tokens}
    token_id_map = _get_token_id_map()
    stablecoin_symbols = {sym for sym, info in token_id_map.items() if info.get('stablecoin')}
    trading_signals, rejections = validate_signals_against_whitelist(
        trading_signals, valid_symbols, stablecoin_symbols
    )
    if rejections:
        logger.warning(
            f"⚠️ Rejected {len(rejections)} invalid signal(s): "
            + ", ".join(f"{r['symbol']}({r['reason']})" for r in rejections)
        )

    # VALIDATION: Check that response contains expected signal patterns
    # The LLM must output signals in the exact format specified in prompts:
    # **$SYMBOL Token Name: SIGNAL TYPE** - reason
    # If it outputs emojis or wrong format, parsing will fail and no backtests will run
    import re

    # Check format validity
    # Match formats like: **$SYMBOL Token: SIGNAL** - reason
    valid_signal_type_re = r'(STRONG\s+BUY|BUY|WEAK\s+BUY|WEAK\s+SELL|SELL|STRONG\s+SELL)'
    format_valid = re.search(
        rf'^\s*\*\*\$[A-Za-z0-9]+\s+[^:]+?:\s+{valid_signal_type_re}\*\*\s*-\s*.+$',
        trading_signals,
        re.IGNORECASE | re.MULTILINE
    )

    # Detect LLM refusal patterns
    refusal_patterns = [
        r'insufficient.*catalyst',
        r'cannot generate signal',
        r'not enough information',
        r'unable to provide',
        r'no actionable',
        r'insufficient.*news',
    ]
    is_refusal = any(re.search(pattern, trading_signals, re.IGNORECASE) for pattern in refusal_patterns)

    # Flag to trigger fallback retry
    retry_with_fallback = False

    if not format_valid:
        error_msg = (
            f"LLM response doesn't match expected signal format (**$SYMBOL Token: SIGNAL** - reason). "
            f"Response length: {len(trading_signals)} chars. "
            f"First 500 chars: {trading_signals[:500]}"
        )
        logger.warning(f"⚠️ {error_msg}")

        if is_refusal:
            logger.warning("⚠️ LLM explicitly refused to generate signals (detected refusal pattern)")
            logger.warning("Triggering fallback retry with more inclusive prompt...")
            retry_with_fallback = True
        else:
            logger.warning("Format issue detected but not a clear refusal - will attempt parsing")
            logger.warning("If parsing fails, fallback will be triggered")

        # Save diagnostic file for debugging (but don't crash)
        diagnostic_file = filename.parent / f"diagnostic_format_warning_{today_str}.txt"
        try:
            with open(diagnostic_file, "w") as f:
                f.write(f"Signal Format Validation Warning\n")
                f.write(f"=================================\n\n")
                f.write(f"Warning: {error_msg}\n\n")
                if is_refusal:
                    f.write(f"Refusal detected: LLM explicitly refused to generate signals\n\n")
                f.write(f"Expected format examples:\n")
                f.write(f"**$BTC Bitcoin: STRONG BUY** - reason\n")
                f.write(f"**$ETH Ethereum: WEAK BUY** - reason\n\n")
                f.write(f"Actual LLM Response:\n")
                f.write(f"{trading_signals}\n\n")
                f.write(f"News items sent ({len(news_data)}):\n")
                f.write(f"{headlines_summary}\n\n")
                f.write(f"Token list sent ({len(tokens_to_include)} tokens):\n")
                f.write(f"{token_list_str[:500]}...\n")
            logger.warning(f"Diagnostic saved: {diagnostic_file}")
        except Exception as diag_error:
            logger.warning(f"Could not save diagnostic file: {diag_error}")

    # Parse signals BEFORE transformation (for backtesting)

    # Run incremental backtest FIRST (before transformation, so parser can read original format)
    backtest_section = ""
    today_signals = []
    if ACTIVE_PROMPT == 'signals':
        try:
            # Initialize signal parser (needed for both initial and fallback parsing)
            signal_parser = SignalParser(WRITEUP_DIR)

            # If format validation detected refusal, skip parsing and trigger fallback immediately
            if not retry_with_fallback:
                if verbose:
                    logger.info("Running incremental backtest...")

                # Parse signals from the original format (before transformation)
                # Create a temporary file with proper filename pattern for parsing
                # The parser requires filename with date pattern: signals_YYYY-MM-DD.md
                temp_dir = Path(tempfile.gettempdir())
                temp_filename = f"signals_{today_str}.md"
                tmp_path = temp_dir / temp_filename

                # Write original format signals to temp file
                with open(tmp_path, 'w') as tmp_file:
                    tmp_file.write(f"## 🎯 Trading Signals\n\n{trading_signals}")

                try:
                    today_signals = signal_parser.parse_file(tmp_path)
                    if verbose and today_signals:
                        logger.info(f"✓ Parsed {len(today_signals)} signals for backtesting")
                except Exception as parse_error:
                    logger.warning(f"⚠️ Signal parsing failed: {parse_error}")
                    logger.warning("Triggering fallback retry with more inclusive prompt...")
                    retry_with_fallback = True
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()
            else:
                logger.info("Skipping initial parsing due to format validation failure, will retry with fallback")

            if today_signals and not retry_with_fallback:
                # Run sentiment-based portfolio strategy
                if verbose:
                    logger.info("Running sentiment-based portfolio strategy...")

                # Initialize sentiment tracker
                sentiment_tracker = SentimentTracker(SENTIMENT_STATE_FILE)

                # Apply decay up to today
                sentiment_tracker.apply_decay(today.date())

                # Apply today's signals
                for signal in today_signals:
                    sentiment_tracker.apply_signal(
                        symbol=signal.symbol,
                        signal_type=signal.signal_type,
                        signal_date=today.date(),
                        token_name=signal.token_name,
                    )

                # Get long/short candidates
                long_candidates = sentiment_tracker.get_long_candidates(n=5)
                short_candidates = sentiment_tracker.get_short_candidates(n=3)

                if verbose:
                    logger.info(f"  Long candidates: {long_candidates}")
                    logger.info(f"  Short candidates: {short_candidates}")

                # Fetch prices for candidates
                price_fetcher = PriceFetcher()
                all_candidates = set(long_candidates + short_candidates)
                prices = {}
                token_names = {}

                for symbol in all_candidates:
                    price = price_fetcher.get_price(symbol, today)
                    if price:
                        prices[symbol] = price
                        token_sentiment = sentiment_tracker.sentiments.get(symbol)
                        if token_sentiment and token_sentiment.token_name:
                            token_names[symbol] = token_sentiment.token_name
                    else:
                        if verbose:
                            logger.warning(f"  Could not fetch price for {symbol}")

                price_fetcher.close()

                # Filter candidates to only those with prices
                long_targets = [s for s in long_candidates if s in prices]
                short_targets = [s for s in short_candidates if s in prices]

                if long_targets or short_targets:
                    # === MOMENTUM STRATEGY ===
                    # Long positive sentiment, short negative sentiment
                    momentum_portfolio = SentimentPortfolio.load(
                        SENTIMENT_PORTFOLIO_STATE_FILE,
                        initial_capital=BACKTEST_INITIAL_CAPITAL
                    )

                    sentiment_scores = dict(sentiment_tracker.get_ranked_tokens())

                    momentum_results = momentum_portfolio.rebalance(
                        long_targets=long_targets,
                        short_targets=short_targets,
                        prices=prices,
                        date=today,
                        token_names=token_names,
                        sentiments=sentiment_scores,
                    )

                    momentum_portfolio.save(SENTIMENT_PORTFOLIO_STATE_FILE)

                    if verbose:
                        logger.info(f"✓ Momentum portfolio: ${momentum_results['total_value']:,.2f}")

                    # === CONTRARIAN STRATEGY ===
                    # Long negative sentiment (mean reversion), short positive sentiment
                    contrarian_portfolio = SentimentPortfolio.load(
                        SENTIMENT_PORTFOLIO_INVERSE_STATE_FILE,
                        initial_capital=BACKTEST_INITIAL_CAPITAL
                    )

                    contrarian_results = contrarian_portfolio.rebalance(
                        long_targets=short_targets,   # Inverted: long the shorts
                        short_targets=long_targets,   # Inverted: short the longs
                        prices=prices,
                        date=today,
                        token_names=token_names,
                        sentiments=sentiment_scores,
                    )

                    contrarian_portfolio.save(SENTIMENT_PORTFOLIO_INVERSE_STATE_FILE)

                    if verbose:
                        logger.info(f"✓ Contrarian portfolio: ${contrarian_results['total_value']:,.2f}")

                    # Save sentiment state
                    sentiment_tracker.last_processed_date = today.date().isoformat()
                    sentiment_tracker.save()

                    # Format both for newsletter
                    sentiment_rankings = sentiment_tracker.get_ranked_tokens()
                    backtest_section = "\n\n" + format_dual_sentiment_portfolios(
                        momentum_results=momentum_results,
                        contrarian_results=contrarian_results,
                        sentiment_rankings=sentiment_rankings,
                        initial_capital=BACKTEST_INITIAL_CAPITAL,
                        btc_price=prices.get('BTC'),
                    )
                else:
                    sentiment_tracker.last_processed_date = today.date().isoformat()
                    sentiment_tracker.save()
                    if verbose:
                        logger.warning("No prices available for sentiment candidates (continuing without portfolio section)")
            else:
                # VALIDATION: Trigger fallback retry if:
                # 1. Format validation detected refusal (retry_with_fallback flag set)
                # 2. Signal generation produced zero signals despite having news and tokens
                if retry_with_fallback or (len(news_data) > 0 and len(tokens_to_include) > 0):
                    if retry_with_fallback:
                        logger.warning("Format validation detected issue - retrying with fallback (more inclusive) prompt...")
                    else:
                        logger.warning(
                            f"Initial signal generation produced ZERO signals despite having "
                            f"{len(news_data)} news items and {len(tokens_to_include)} tracked tokens. "
                            f"This may indicate the prompt was too strict. Retrying with fallback (more inclusive) prompt..."
                        )

                    # RETRY: Use fallback prompt that's more inclusive
                    try:
                        if verbose:
                            logger.info("Retrying signal generation with fallback prompt...")

                        fallback_prompt = get_fallback_system_message()
                        retry_signals = await engine.generate_writeup_with_prompt(
                            headlines=headlines_summary,
                            token_list=token_list_str,
                            system_message=fallback_prompt,  # Use fallback instead of default
                            prompt_type="signals"
                        )

                        # Check if retry produced signals
                        if retry_signals and len(retry_signals.strip()) > 50:
                            # Validate fallback response format
                            fallback_format_valid = re.search(
                                rf'^\s*\*\*\$[A-Za-z0-9]+\s+[^:]+?:\s+{valid_signal_type_re}\*\*\s*-\s*.+$',
                                retry_signals,
                                re.IGNORECASE | re.MULTILINE
                            )
                            fallback_is_refusal = any(re.search(pattern, retry_signals, re.IGNORECASE) for pattern in refusal_patterns)

                            if not fallback_format_valid:
                                logger.error("CRITICAL: Fallback prompt ALSO failed to generate valid signals")
                                logger.error(f"Response length: {len(retry_signals)} chars")
                                logger.error(f"First 500 chars: {retry_signals[:500]}")

                                # Save diagnostic for fallback failure
                                fallback_diagnostic_file = filename.parent / f"diagnostic_fallback_failure_{today_str}.txt"
                                try:
                                    with open(fallback_diagnostic_file, "w") as f:
                                        f.write(f"BOTH Strict AND Fallback Prompts Failed\n")
                                        f.write(f"==========================================\n\n")
                                        f.write(f"Strict prompt response:\n{trading_signals[:1000]}\n\n")
                                        f.write(f"Fallback prompt response:\n{retry_signals[:1000]}\n\n")
                                        if fallback_is_refusal:
                                            f.write(f"Fallback also contained refusal pattern\n\n")
                                        f.write(f"News items: {len(news_data)}\n")
                                        f.write(f"Tokens: {len(tokens_to_include)}\n")
                                    logger.error(f"Diagnostic saved: {fallback_diagnostic_file}")
                                except Exception:
                                    pass

                                # Instead of crashing, continue with empty signals
                                logger.warning(
                                    "⚠️ Both strict and fallback prompts failed to generate valid signals. "
                                    "Continuing with empty signals section. See diagnostic file for details."
                                )
                                trading_signals = "*No valid trading signals could be generated today.*"
                                today_signals = []
                            else:
                                logger.info("✓ Fallback prompt generated signals successfully")
                                # Use retry results and coerce HOLD/NEUTRAL-like labels if needed
                                retry_signals = canonicalize_trading_signals_to_bold_lines(retry_signals)
                                trading_signals, coercion_changes = coerce_trading_signals_to_supported_types(
                                    retry_signals,
                                    allow_hold_coercion=True,
                                )
                                if coercion_changes:
                                    logger.warning(
                                        f"⚠️ Coerced {len(coercion_changes)} invalid signal label(s) to supported types "
                                        f"(saved in output for pipeline safety)"
                                    )

                                # Validate retry signals against whitelist
                                trading_signals, retry_rejections = validate_signals_against_whitelist(
                                    trading_signals, valid_symbols, stablecoin_symbols
                                )
                                if retry_rejections:
                                    logger.warning(
                                        f"⚠️ Rejected {len(retry_rejections)} invalid retry signal(s): "
                                        + ", ".join(f"{r['symbol']}({r['reason']})" for r in retry_rejections)
                                    )

                                # Re-parse signals from retry
                                temp_dir = Path(tempfile.gettempdir())
                                temp_filename = f"signals_{today_str}_retry.md"
                                tmp_path = temp_dir / temp_filename

                                with open(tmp_path, 'w') as tmp_file:
                                    tmp_file.write(f"## 🎯 Trading Signals\n\n{trading_signals}")

                                try:
                                    today_signals = signal_parser.parse_file(tmp_path)
                                    if verbose and today_signals:
                                        logger.info(f"✓ Parsed {len(today_signals)} signals from retry for backtesting")
                                finally:
                                    if tmp_path.exists():
                                        tmp_path.unlink()

                                # If parsing still failed, try one more time with canonicalized output.
                                if not today_signals:
                                    logger.warning("⚠️ Retry signals still did not parse; attempting canonicalization+reparse")
                                    canonical = canonicalize_trading_signals_to_bold_lines(trading_signals)
                                    canonical, _ = coerce_trading_signals_to_supported_types(
                                        canonical,
                                        allow_hold_coercion=True,
                                    )

                                    tmp_path = temp_dir / f"signals_{today_str}_retry_canonical.md"
                                    with open(tmp_path, 'w') as tmp_file:
                                        tmp_file.write(f"## 🎯 Trading Signals\n\n{canonical}")
                                    try:
                                        today_signals = signal_parser.parse_file(tmp_path)
                                        if verbose and today_signals:
                                            logger.info(f"✓ Parsed {len(today_signals)} signals after canonicalization")
                                    finally:
                                        if tmp_path.exists():
                                            tmp_path.unlink()

                            # Continue with sentiment portfolio using retry signals
                            if today_signals:
                                if verbose:
                                    logger.info("Running sentiment-based portfolio strategy with retry signals...")

                                # Initialize sentiment tracker
                                sentiment_tracker = SentimentTracker(SENTIMENT_STATE_FILE)

                                # Apply decay up to today
                                sentiment_tracker.apply_decay(today.date())

                                # Apply today's signals
                                for signal in today_signals:
                                    sentiment_tracker.apply_signal(
                                        symbol=signal.symbol,
                                        signal_type=signal.signal_type,
                                        signal_date=today.date(),
                                        token_name=signal.token_name,
                                    )

                                # Get long/short candidates
                                long_candidates = sentiment_tracker.get_long_candidates(n=5)
                                short_candidates = sentiment_tracker.get_short_candidates(n=3)

                                if verbose:
                                    logger.info(f"  Long candidates: {long_candidates}")
                                    logger.info(f"  Short candidates: {short_candidates}")

                                # Fetch prices for candidates
                                retry_price_fetcher = PriceFetcher()
                                all_candidates = set(long_candidates + short_candidates)
                                prices = {}
                                token_names = {}

                                for symbol in all_candidates:
                                    price = retry_price_fetcher.get_price(symbol, today)
                                    if price:
                                        prices[symbol] = price
                                        token_sentiment = sentiment_tracker.sentiments.get(symbol)
                                        if token_sentiment and token_sentiment.token_name:
                                            token_names[symbol] = token_sentiment.token_name
                                    else:
                                        if verbose:
                                            logger.warning(f"  Could not fetch price for {symbol}")

                                retry_price_fetcher.close()

                                # Filter candidates to only those with prices
                                long_targets = [s for s in long_candidates if s in prices]
                                short_targets = [s for s in short_candidates if s in prices]

                                if long_targets or short_targets:
                                    retry_sentiment_scores = dict(sentiment_tracker.get_ranked_tokens())

                                    # === MOMENTUM STRATEGY ===
                                    momentum_portfolio = SentimentPortfolio.load(
                                        SENTIMENT_PORTFOLIO_STATE_FILE,
                                        initial_capital=BACKTEST_INITIAL_CAPITAL
                                    )

                                    momentum_results = momentum_portfolio.rebalance(
                                        long_targets=long_targets,
                                        short_targets=short_targets,
                                        prices=prices,
                                        date=today,
                                        token_names=token_names,
                                        sentiments=retry_sentiment_scores,
                                    )

                                    momentum_portfolio.save(SENTIMENT_PORTFOLIO_STATE_FILE)

                                    if verbose:
                                        logger.info(f"✓ Momentum portfolio (retry): ${momentum_results['total_value']:,.2f}")

                                    # === CONTRARIAN STRATEGY ===
                                    contrarian_portfolio = SentimentPortfolio.load(
                                        SENTIMENT_PORTFOLIO_INVERSE_STATE_FILE,
                                        initial_capital=BACKTEST_INITIAL_CAPITAL
                                    )

                                    contrarian_results = contrarian_portfolio.rebalance(
                                        long_targets=short_targets,   # Inverted
                                        short_targets=long_targets,   # Inverted
                                        prices=prices,
                                        date=today,
                                        token_names=token_names,
                                        sentiments=retry_sentiment_scores,
                                    )

                                    contrarian_portfolio.save(SENTIMENT_PORTFOLIO_INVERSE_STATE_FILE)

                                    if verbose:
                                        logger.info(f"✓ Contrarian portfolio (retry): ${contrarian_results['total_value']:,.2f}")

                                    # Save sentiment state
                                    sentiment_tracker.last_processed_date = today.date().isoformat()
                                    sentiment_tracker.save()

                                    # Format both for newsletter
                                    sentiment_rankings = sentiment_tracker.get_ranked_tokens()
                                    backtest_section = "\n\n" + format_dual_sentiment_portfolios(
                                        momentum_results=momentum_results,
                                        contrarian_results=contrarian_results,
                                        sentiment_rankings=sentiment_rankings,
                                        initial_capital=BACKTEST_INITIAL_CAPITAL,
                                        btc_price=prices.get('BTC'),
                                    )
                                else:
                                    sentiment_tracker.last_processed_date = today.date().isoformat()
                                    sentiment_tracker.save()
                                    if verbose:
                                        logger.warning("No prices available for sentiment candidates (continuing without portfolio section)")
                        else:
                            # Fallback also failed
                            error_msg = (
                                f"CRITICAL: Both initial AND fallback signal generation failed. "
                                f"Initial response: {len(trading_signals)} chars, Retry response: {len(retry_signals) if retry_signals else 0} chars. "
                                f"This indicates a systemic LLM issue or API failure."
                            )
                            logger.error(error_msg)
                            raise ValueError(error_msg)

                    except ValueError:
                        # Re-raise ValueError (real errors)
                        raise
                    except Exception as e:
                        logger.error(f"Error during retry: {e}", exc_info=True)
                        error_msg = (
                            f"CRITICAL: Retry with fallback prompt failed with exception: {e}. "
                            f"Original generation also produced zero signals."
                        )
                        raise ValueError(error_msg)
                else:
                    if verbose:
                        logger.info("No signals found for today (no news/tokens available), skipping backtest")
        except ValueError as e:
            # Re-raise validation errors (e.g., zero signals when data exists)
            logger.error(f"Signal validation failed: {e}")
            raise
        except Exception as e:
            logger.warning(f"Error running backtest: {e}", exc_info=True)
            # Continue without backtest section for other errors
    
    # NOW transform trading signals to new format (after parsing for backtest)
    trading_signals = transform_trading_signals_markdown(trading_signals)
    
    # Remove any H1 headers (like "Trading Signals - Leviathan News Edition") that might be in the AI response
    import re
    trading_signals = re.sub(r'^#\s+.*?Trading Signals.*?$', '', trading_signals, flags=re.MULTILINE | re.IGNORECASE)
    
    # Filter out any non-signal sections (like "Market Context", "---" separators, etc.)
    # Split by lines and extract only trading signals (lines starting with emoji)
    signal_lines = trading_signals.strip().split('\n')
    formatted_signals = []
    in_signals_section = True
    
    for line in signal_lines:
        line_stripped = line.strip()
        
        # Skip empty lines, separators, and section headers
        if not line_stripped:
            continue
        if line_stripped.startswith('---'):
            continue
        if re.match(r'^##+\s+', line_stripped):  # Skip any markdown headers (like "## Market Context")
            in_signals_section = False
            continue
        
        # Only process lines that look like trading signals (start with emoji)
        # This filters out any extra content the LLM might generate
        if any(line_stripped.startswith(emoji) for emoji in ['🟢', '🔴', '🟡', '🟠', '⚪']):
            in_signals_section = True
            # Check if multiple signals are on the same line (split them)
            # Count emojis in the line - if more than one, we need to split
            emoji_count = sum(1 for c in line_stripped if c in ['🟢', '🔴', '🟡', '🟠', '⚪'])
            
            if emoji_count > 1:
                # Multiple signals on same line - split them
                emoji_pattern = r'([🟢🔴🟡🟠⚪])'
                # Split the line at each emoji occurrence (but keep the emoji)
                parts = re.split(emoji_pattern, line_stripped)
                # Reconstruct signals: each emoji starts a new signal
                current_signal = ""
                for part in parts:
                    if part in ['🟢', '🔴', '🟡', '🟠', '⚪']:
                        # New signal starting - save previous if exists
                        if current_signal and current_signal.strip():
                            formatted_signals.append(current_signal.strip())
                        current_signal = part
                    elif part and part.strip():  # Skip empty strings
                        current_signal += part
                # Add the last signal
                if current_signal and current_signal.strip():
                    formatted_signals.append(current_signal.strip())
            else:
                # Single signal on line - use as-is
                formatted_signals.append(line_stripped)
        elif in_signals_section and line_stripped:
            # If we're in signals section but this isn't a signal, skip it
            # (this filters out any stray content)
            continue
    
    # Join signals with double line breaks to ensure proper spacing
    trading_signals = '\n\n'.join(formatted_signals)

    # CRITICAL VALIDATION: Fail early if no signals survived the transformation/filtering
    # This catches the case where LLM output didn't match expected format and transform
    # produced no emoji-prefixed lines. Better to fail here than write an empty file.
    if not formatted_signals or len(trading_signals.strip()) < 50:
        error_msg = (
            f"CRITICAL: Signal transformation produced no valid signals! "
            f"This indicates the LLM output didn't match expected format (**$SYMBOL Token: SIGNAL** - reason). "
            f"Formatted signals count: {len(formatted_signals)}. "
            f"Transformed content length: {len(trading_signals.strip())} chars. "
            f"Original today_signals count: {len(today_signals)}. "
            f"Check diagnostic files for LLM response details."
        )
        logger.error(error_msg)

        # Save diagnostic file
        diagnostic_file = filename.parent / f"diagnostic_empty_signals_{today_str}.txt"
        try:
            with open(diagnostic_file, "w") as f:
                f.write(f"Empty Signals After Transformation\n")
                f.write(f"===================================\n\n")
                f.write(f"Error: {error_msg}\n\n")
                f.write(f"formatted_signals list: {formatted_signals}\n\n")
                f.write(f"trading_signals after join: '{trading_signals}'\n\n")
                f.write(f"today_signals (parsed): {len(today_signals)} signals\n")
                for i, sig in enumerate(today_signals[:10]):
                    f.write(f"  {i+1}. {sig}\n")
            logger.error(f"Diagnostic file saved: {diagnostic_file}")
        except Exception as diag_error:
            logger.error(f"Could not save diagnostic file: {diag_error}")

        raise ValueError(error_msg)

    # Generate market snapshot
    if verbose:
        logger.info("Generating market snapshot...")
    market_snapshot_section = generate_market_snapshot(verbose=verbose)

    # Combine all sections (header, market snapshot, top stories with SQUID Pass winner in same table)
    # Note: top_stories_section already includes the "## 🔥 Top Stories" header and table tags
    # We need to insert SQUID Pass winner row at the start of the table
    top_stories_header = "## 🔥 Top Stories\n\n"
    top_stories_content = top_stories_section.replace(top_stories_header, "")
    
    # Insert SQUID Pass winner row at the start of the table (after <table> tag)
    if squid_pass_section and "<table" in top_stories_content:
        # Find the table opening tag (could be <table> or <table style=...>)
        import re
        # Match <table> or <table with any attributes
        table_match = re.search(r'<table[^>]*>', top_stories_content)
        if table_match:
            table_end = table_match.end()
            # Insert SQUID Pass row right after <table> opening tag
            top_stories_content = (
                top_stories_content[:table_end] + 
                "\n" + squid_pass_section + 
                top_stories_content[table_end:]
            )
    
    full_writeup = f"""# 📊 Crypto Trading Signals - {datetime.now().strftime('%B %d, %Y')}
{market_snapshot_section}
{top_stories_header}{top_stories_content}
## 🎯 Trading Signals

{trading_signals}"""

    # Append backtest section if available (before writing file)
    if backtest_section:
        full_writeup += "\n" + backtest_section
        # Footer after backtest section
        full_writeup += "\n\n---\n*Disclaimer: Trading strategies generated by AI, which is wrong about everything, so you'd have to be a complete "
    else:
        # CRITICAL VALIDATION: If we have trading signals but NO backtest section, something went wrong
        # This indicates signal parsing failed (likely due to format mismatch)
        if trading_signals and len(trading_signals.strip()) > 50:
            error_msg = (
                f"CRITICAL: Trading signals were generated but backtest section is missing! "
                f"This indicates signal parsing failed, likely due to LLM format mismatch. "
                f"Signals length: {len(trading_signals)} chars. "
                f"Check diagnostic files for details."
            )
            logger.error(error_msg)

            # Save diagnostic file
            diagnostic_file = filename.parent / f"diagnostic_no_backtest_{today_str}.txt"
            try:
                with open(diagnostic_file, "w") as f:
                    f.write(f"Backtest Section Missing\n")
                    f.write(f"========================\n\n")
                    f.write(f"Error: {error_msg}\n\n")
                    f.write(f"Trading signals generated ({len(trading_signals)} chars):\n")
                    f.write(f"{trading_signals}\n\n")
                    f.write(f"Expected format: **$SYMBOL Token: SIGNAL** - reason\n")
                    f.write(f"Parsed signals count: {len(today_signals)}\n")
                logger.error(f"Diagnostic file saved to: {diagnostic_file}")
            except Exception as diag_error:
                logger.error(f"Could not save diagnostic file: {diag_error}")

            raise ValueError(error_msg)

        # Footer without backtest section (add blank line before separator)
        full_writeup += "\n\n---\n*Disclaimer: Trading strategies generated by AI, which is wrong about everything, so you'd have to be a complete "
    moron_synonym = random.choice(MORON_SYNONYMS)
    full_writeup += f"{moron_synonym} to take financial advice from one!*"
    
    if verbose:
        logger.info(f"Writing trading signals to: {Path(filename).absolute()}")
    
    with open(filename, "w") as f:
        f.write(full_writeup)

    if verbose:
        logger.info(f"✓ Created: {filename}")
        logger.info("Trading signals generation completed successfully")

    # --- Generate blurb and write distribution metadata ---
    title = f"Crypto Trading Signals - {today.strftime('%B %d, %Y')}"
    blurb = DEFAULT_BLURB
    try:
        # Extract a one-sentence blurb from the first few headlines
        headline_texts = [s.get("headline", "") for s in news_data[:5] if s.get("headline")]
        if headline_texts:
            short_headlines = " • ".join(h[:60] for h in headline_texts[:3])
            blurb = short_headlines
        if verbose:
            logger.info(f"Blurb: {blurb}")
    except Exception as blurb_err:
        logger.warning(f"Could not generate blurb: {blurb_err}")

    save_meta(today, {"blurb": blurb, "date": today_str, "title": title})
    if verbose:
        logger.info("✓ Distribution metadata saved")

    # Generate RSS feed
    if verbose:
        logger.info("Generating RSS feed...")

    try:
        from squid_digest.rss.feed_generator import RSSFeedGenerator
        from squid_digest.rss.digest_scanner import DigestScanner

        scanner = DigestScanner(WRITEUP_DIR)
        digests = scanner.scan(limit=30, file_pattern="signals_*.md")

        generator = RSSFeedGenerator()
        feed_path = WRITEUP_DIR / "feed.xml"
        items_added = generator.generate_feed(digests, feed_path)

        if verbose:
            logger.info(f"✓ Generated RSS feed: {feed_path} ({items_added} items)")
    except Exception as e:
        logger.warning(f"Could not generate RSS feed: {e}")
        # Continue without RSS (non-critical)


async def main(fetch=True, limit=10, each_news=False, bundle=True, verbose=False, resolve_urls=False, fetch_tokens_flag=True):
    if verbose:
        logger.info("=" * 60)
        logger.info("SQUID DIGEST - Starting Process")
        logger.info("=" * 60)
        logger.info(f"Configuration:")
        logger.info(f"  - Fetch news: {fetch}")
        logger.info(f"  - Fetch tokens: {fetch_tokens_flag}")
        logger.info(f"  - Limit: {limit}")
        logger.info(f"  - Individual writeups: {each_news}")
        logger.info(f"  - Trading signals: {bundle}")
        logger.info(f"  - Verbose logging: {verbose}")
        logger.info("=" * 60)
    
    if fetch:
        logger.info("Fetching news from Leviathan News")
        fetch_news(limit, verbose, resolve_urls)
    if fetch_tokens_flag:
        logger.info("Fetching token list from Leviathan News")
        fetch_tokens(verbose)
    if each_news:
        logger.info("Generating writeup for each news content")
        await each_news_content(limit, verbose)
    if bundle:
        logger.info("Generating trading signals for all news content")
        await bundle_writeup(verbose)
    
    if verbose:
        logger.info("=" * 60)
        logger.info("SQUID DIGEST - Process Completed")
        logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate AI-powered trading signals from Leviathan News")
    parser.add_argument("--limit", type=int, default=10, help="Number of news items to fetch (default: 10)")
    parser.add_argument("--no-fetch", action="store_true", help="Skip fetching news (use cached data)")
    parser.add_argument("--no-fetch-tokens", action="store_true", help="Skip fetching tokens (use cached data)")
    parser.add_argument("--resolve-urls", action="store_true", help="Resolve redirect URLs (slow, only needed for AI analysis)")
    parser.add_argument("--each-news", action="store_true", help="Generate writeup for each news item individually")
    parser.add_argument("--no-bundle", action="store_true", help="Skip generating trading signals")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging to show file operations")
    
    args = parser.parse_args()
    
    # Set up logging level based on verbose flag
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Convert argparse args to main() parameters
    fetch = not args.no_fetch
    fetch_tokens_flag = not args.no_fetch_tokens
    each_news = args.each_news
    bundle = not args.no_bundle
    
    asyncio.run(main(fetch=fetch, limit=args.limit, each_news=each_news, bundle=bundle, verbose=args.verbose, resolve_urls=args.resolve_urls, fetch_tokens_flag=fetch_tokens_flag))
