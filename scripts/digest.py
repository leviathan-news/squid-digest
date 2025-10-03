"""
Script for generating writeup for each news content or bundle all news content
"""

import asyncio, json, argparse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
from squid_digest.tools.leviathan import LeviathanNewsFetcher
from squid_digest.core.digest_engine import DigestEngine
from squid_digest.llm import OpenAIChatProvider
from squid_digest.config import WRITEUP_DIR
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_news(limit=5):
    leviathan_news_fetcher = LeviathanNewsFetcher()
    news = leviathan_news_fetcher.fetch_news(limit=limit)
    news_with_redirect_url = leviathan_news_fetcher.get_redirect_url(news)
    news_with_content = leviathan_news_fetcher.fetch_news_content(
        news_with_redirect_url
    )


async def each_news_content(limit=5):
    """
    Generate writeup for each news content

    Args:
        limit: Just to be safe in case the file has lot of news
    """
    engine = DigestEngine(
        news_fetcher=LeviathanNewsFetcher(),
        llm_chat_provider=OpenAIChatProvider(),
    )
    with open(".data/leviathan_news_content.json", "r") as f:
        news_content = json.load(f)
    for content in news_content[:limit]:
        response_content = await engine.generate_writeup(
            content["content"]
        )  # TODO: add title, description to promt
        today = datetime.now().strftime("%Y-%m-%d")
        with open(f"{WRITEUP_DIR}/writeup_{today}_id_{content['id']}.md", "w") as f:
            f.write(response_content)


async def bundle_writeup():
    engine = DigestEngine(
        news_fetcher=LeviathanNewsFetcher(),
        llm_chat_provider=OpenAIChatProvider(),
    )
    with open(".data/leviathan_news_content.json", "r") as f:
        news_content = json.load(f)

    bundled_content = "\n\n".join([content["content"] for content in news_content])
    response_content = await engine.generate_writeup(bundled_content)
    today = datetime.now().strftime("%Y-%m-%d")
    with open(f"{WRITEUP_DIR}/writeup_bundled_{today}.md", "w") as f:
        f.write(response_content)


async def main(fetch=False, limit=5, each_news=False, bundle=True):
    if fetch:
        logger.info("Fetching news from Leviathan News")
        fetch_news(limit)
    if each_news:
        logger.info("Generating writeup for each news content")
        await each_news_content(limit)
    if bundle:
        logger.info("Bundling writeup for all news content")
        await bundle_writeup()


if __name__ == "__main__":
    asyncio.run(main())
