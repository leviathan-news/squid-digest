"""Backfill daily video-script artifacts from archived signals files.

Examples:
    uv run python scripts/backfill_video_scripts.py
    uv run python scripts/backfill_video_scripts.py --days 7
    uv run python scripts/backfill_video_scripts.py --dates 2026-04-29 2026-04-27
"""

import argparse
import asyncio
import html
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from squid_digest.config import WRITEUP_DIR, get_writeup_file_path, load_meta
from squid_digest.tools.leviathan import LeviathanNewsFetcher
from squid_digest.llm import PerplexityChatProvider
from squid_digest.core.digest_engine import DigestEngine

from digest import generate_video_script

logger = logging.getLogger(__name__)

TOP_STORIES_SECTION_RE = re.compile(r"## 🔥 Top Stories\s*(.+?)(?=\n## |\Z)", re.DOTALL)
TOP_STORY_HEADLINE_RE = re.compile(
    r"<p[^>]*>\s*\d+\.\s*(.*?)\s*-\s*<a\b",
    re.IGNORECASE | re.DOTALL,
)
HTML_TAG_RE = re.compile(r"<[^>]+>")
SIGNALS_FILENAME_RE = re.compile(r"signals_(\d{4}-\d{2}-\d{2})\.md$")


def parse_iso_date(value):
    """Parse YYYY-MM-DD strings for CLI date arguments."""
    return datetime.strptime(value, "%Y-%m-%d")


def extract_top_story_headlines(content, limit=5):
    """Extract plain headline text from the archived Top Stories section."""
    section_match = TOP_STORIES_SECTION_RE.search(content)
    if not section_match:
        return []

    headlines = []
    for raw_headline in TOP_STORY_HEADLINE_RE.findall(section_match.group(1)):
        cleaned = html.unescape(HTML_TAG_RE.sub("", raw_headline))
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            headlines.append(cleaned)
        if len(headlines) >= limit:
            break
    return headlines


def load_headlines_for_date(target_date):
    """Load archived headlines for *target_date* from signals markdown, with meta fallback."""
    date_str = target_date.strftime("%Y-%m-%d")
    signals_path = get_writeup_file_path(f"signals_{date_str}.md", target_date)
    if not signals_path.exists():
        logger.info("No signals file for %s, skipping", date_str)
        return []

    headlines = extract_top_story_headlines(signals_path.read_text())
    if headlines:
        return headlines

    meta = load_meta(target_date)
    fallback_headlines = []
    top_story_headline = meta.get("top_story_headline", "").strip()
    blurb = meta.get("blurb", "").strip()

    if top_story_headline:
        fallback_headlines.append(top_story_headline)
    if blurb and blurb not in fallback_headlines:
        fallback_headlines.append(blurb)

    if fallback_headlines:
        logger.info("Top Stories parse failed for %s, using meta fallback", date_str)
    else:
        logger.warning("Could not recover any headlines for %s", date_str)
    return fallback_headlines


def find_recent_signal_dates(limit=5, writeup_dir=WRITEUP_DIR):
    """Return the most recent *limit* signal dates, skipping missing calendar days."""
    available_dates = set()
    for path in writeup_dir.rglob("signals_*.md"):
        match = SIGNALS_FILENAME_RE.match(path.name)
        if match:
            available_dates.add(parse_iso_date(match.group(1)))

    if not available_dates:
        return []

    selected_dates = []
    cursor = max(available_dates)
    earliest = min(available_dates)

    while len(selected_dates) < limit and cursor >= earliest:
        if cursor in available_dates:
            selected_dates.append(cursor)
        else:
            logger.info("No signals file for %s, skipping", cursor.strftime("%Y-%m-%d"))
        cursor -= timedelta(days=1)

    return selected_dates


async def backfill_video_scripts(target_dates, verbose=False):
    """Generate historical video scripts for the provided dates."""
    if not target_dates:
        logger.warning("No target dates found for video-script backfill")
        return

    engine = DigestEngine(
        news_fetcher=LeviathanNewsFetcher(),
        llm_chat_provider=PerplexityChatProvider(),
    )

    for target_date in target_dates:
        headlines = load_headlines_for_date(target_date)
        if not headlines:
            continue

        if verbose:
            date_str = target_date.strftime("%Y-%m-%d")
            logger.info("Backfilling video script for %s", date_str)

        await generate_video_script(engine, headlines, target_date, verbose=verbose)


def build_target_dates(days=5, dates=None):
    """Resolve CLI target dates."""
    if dates:
        return dates
    return find_recent_signal_dates(limit=days)


def main():
    parser = argparse.ArgumentParser(description="Backfill daily SQUID Digest video scripts")
    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="Number of recent signal dates to backfill (default: 5)",
    )
    parser.add_argument(
        "--dates",
        nargs="+",
        type=parse_iso_date,
        help="Explicit dates to backfill in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    target_dates = build_target_dates(days=args.days, dates=args.dates)
    asyncio.run(backfill_video_scripts(target_dates, verbose=args.verbose))


if __name__ == "__main__":
    main()
