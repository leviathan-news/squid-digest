"""
Script for generating writeup for each news content or bundle all news content
"""

import asyncio, json, argparse
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
from squid_digest.tools.leviathan import LeviathanNewsFetcher
from squid_digest.core.digest_engine import DigestEngine
from squid_digest.llm import PerplexityChatProvider
from squid_digest.config import WRITEUP_DIR
import logging

logger = logging.getLogger(__name__)


def generate_top_stories_section(news_data, limit=5):
    """
    Generate a formatted top stories section from Leviathan News data.
    
    Args:
        news_data: List of news items from Leviathan API
        limit: Number of top stories to include
        
    Returns:
        Formatted markdown string for the top stories section
    """
    top_stories = news_data[:limit]
    
    section = "## 🔥 Top Stories\n\n"
    section += "<table>\n"
    
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
                tag_links.append(f'<a href="https://leviathannews.xyz/tag/{tag_id}/{tag_slug}">{tag_name}</a>')
        
        tags_str = " • ".join(tag_links) if tag_links else ""
        
        # Get top comment if available
        top_comment = ""
        if top_yaps:
            top_yap = top_yaps[0]  # Highest scored comment
            comment_text = top_yap.get('text', '')
            comment_author = top_yap.get('author', {}).get('display_name', 'Anonymous')
            if comment_text:
                top_comment = f"💬 <i>{comment_text}</i> — @{comment_author}"
        
        # Format as HTML table row
        section += "  <tr>\n"
        
        # Image cell
        section += "    <td style=\"width: 140px; vertical-align: center; padding-right: 12px;\">\n"
        if media_url:
            section += f"      <img src=\"{media_url}\" alt=\"Story Image\" width=\"120\" style=\"border-radius: 4px;\">\n"
        section += "    </td>\n"
        
        # Content cell
        section += "    <td style=\"vertical-align: center;\">\n"
        # Link headline to Leviathan article, source to original URL
        leviathan_url = f"https://leviathannews.xyz/news/{story.get('id', '')}"
        section += f"      <strong><a href=\"{leviathan_url}\">{i}. {headline}</a></strong> - <a href=\"{url}\">{source}</a>\n"
        
        if tags_str:
            section += f"      <br><span style=\"font-size: 0.9em;\">🏷️ {tags_str}</span>\n"
        
        if top_comment:
            section += f"      <br>{top_comment}\n"
        
        section += "    </td>\n"
        section += "  </tr>\n"
    
    section += "</table>\n\n"
    
    return section


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
            content["content"]
        )  # TODO: add title, description to promt
        
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"{WRITEUP_DIR}/writeup_{today}_id_{content['id']}.md"
        
        if verbose:
            logger.info(f"Writing writeup to: {Path(filename).absolute()}")
        
        with open(filename, "w") as f:
            f.write(response_content)
        
        if verbose:
            logger.info(f"✓ Created: {filename}")
    
    if verbose:
        logger.info("Individual writeup generation completed successfully")


async def bundle_writeup(verbose=False):
    if verbose:
        logger.info("Starting bundled writeup generation")
        logger.info(f"Creating/using writeup directory: {WRITEUP_DIR.absolute()}")
    
    engine = DigestEngine(
        news_fetcher=LeviathanNewsFetcher(),
        llm_chat_provider=PerplexityChatProvider(),
    )
    
    # Read the raw news data
    data_file = Path(".data/leviathan_news.json")
    if verbose:
        logger.info(f"Reading news data from: {data_file.absolute()}")
    
    with open(data_file, "r") as f:
        news_data = json.load(f)
    
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
    
    # Generate the top stories section
    top_stories_section = generate_top_stories_section(news_data, limit=5)
    
    if verbose:
        logger.info("Generating AI analysis section...")
    
    # Create a summary of headlines for the AI to analyze (use 10 for more context)
    # Use resolved URLs instead of tracking URLs, with proper citation format
    headlines_summary = "\n".join([
        f"[{i+1}] {story.get('headline', 'No headline')} - {redirect_map.get(story.get('id'), story.get('url', 'No URL'))}"
        for i, story in enumerate(news_data[:10])
    ])
    
    # Generate AI analysis
    if verbose:
        logger.info("Headlines being sent to AI:")
        logger.info(headlines_summary)
    
    ai_analysis = await engine.generate_writeup(headlines_summary)
    
    # Combine both sections
    full_writeup = f"""# 📰 Crypto Digest - {datetime.now().strftime('%B %d, %Y')}

{top_stories_section}

## 🤖 AI Analysis

{ai_analysis}

---
*Generated by Squid Digest - Your daily crypto news companion*"""
    
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{WRITEUP_DIR}/writeup_bundled_{today}.md"
    
    if verbose:
        logger.info(f"Writing bundled writeup to: {Path(filename).absolute()}")
    
    with open(filename, "w") as f:
        f.write(full_writeup)
    
    if verbose:
        logger.info(f"✓ Created: {filename}")
        logger.info("Bundled writeup generation completed successfully")


async def main(fetch=True, limit=10, each_news=False, bundle=True, verbose=False, resolve_urls=False):
    if verbose:
        logger.info("=" * 60)
        logger.info("SQUID DIGEST - Starting Process")
        logger.info("=" * 60)
        logger.info(f"Configuration:")
        logger.info(f"  - Fetch news: {fetch}")
        logger.info(f"  - Limit: {limit}")
        logger.info(f"  - Individual writeups: {each_news}")
        logger.info(f"  - Bundled writeup: {bundle}")
        logger.info(f"  - Verbose logging: {verbose}")
        logger.info("=" * 60)
    
    if fetch:
        logger.info("Fetching news from Leviathan News")
        fetch_news(limit, verbose, resolve_urls)
    if each_news:
        logger.info("Generating writeup for each news content")
        await each_news_content(limit, verbose)
    if bundle:
        logger.info("Bundling writeup for all news content")
        await bundle_writeup(verbose)
    
    if verbose:
        logger.info("=" * 60)
        logger.info("SQUID DIGEST - Process Completed")
        logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate AI-powered news digests from Leviathan News")
    parser.add_argument("--limit", type=int, default=10, help="Number of news items to fetch (default: 10)")
    parser.add_argument("--no-fetch", action="store_true", help="Skip fetching news (use cached data)")
    parser.add_argument("--resolve-urls", action="store_true", help="Resolve redirect URLs (slow, only needed for AI analysis)")
    parser.add_argument("--each-news", action="store_true", help="Generate writeup for each news item individually")
    parser.add_argument("--no-bundle", action="store_true", help="Skip generating bundled writeup")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging to show file operations")
    
    args = parser.parse_args()
    
    # Set up logging level based on verbose flag
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Convert argparse args to main() parameters
    fetch = not args.no_fetch
    each_news = args.each_news
    bundle = not args.no_bundle
    
    asyncio.run(main(fetch=fetch, limit=args.limit, each_news=each_news, bundle=bundle, verbose=args.verbose, resolve_urls=args.resolve_urls))
