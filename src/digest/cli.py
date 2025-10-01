"""Command-line interface for Squid Digest."""
import sys
import click
from digest.config import config
from digest.clients import LeviathanNewsClient, PerplexityClient, GhostClient
from digest.services import DigestService


@click.command()
@click.option("--limit", default=10, type=int, help="Number of news items to process")
@click.option("--dry-run", is_flag=True, help="Generate digest but don't publish to Ghost")
@click.option("--test", is_flag=True, help="Use test data instead of API call")
def main(limit: int, dry_run: bool, test: bool):
    """
    Pull news from Leviathan API, generate digest with Perplexity, and publish to Ghost.

    Examples:
        digest-news --limit 10
        digest-news --limit 10 --dry-run
        digest-news --test --dry-run
    """
    try:
        # Get news items
        if test:
            items = _get_test_data()
            click.secho(f"Using {len(items)} test news items", fg="green")
        else:
            items = _fetch_news(limit)

        if not items:
            click.secho("No news items to process", fg="yellow")
            return

        # Generate and optionally publish digest
        digest_content = _run_digest_pipeline(items, dry_run)

        # Output results
        if dry_run:
            _display_dry_run_output(digest_content)
        else:
            click.secho("✓ Digest sent to Ghost successfully!", fg="green")

    except Exception as e:
        click.secho(f"Pipeline failed: {e}", fg="red", err=True)
        sys.exit(1)


def _fetch_news(limit: int):
    """Fetch news using LeviathanNewsClient."""
    try:
        client = LeviathanNewsClient()
        items = client.fetch_top_news(limit=limit)
        click.secho(f"✓ Fetched {len(items)} news items", fg="green")
        return items
    except Exception as e:
        click.secho(f"Failed to fetch news: {e}", fg="red", err=True)
        return []


def _run_digest_pipeline(items, dry_run: bool):
    """Run the digest generation and publishing pipeline."""
    # Validate configuration before running
    config.validate()

    # Initialize clients
    leviathan_client = LeviathanNewsClient()
    perplexity_client = PerplexityClient(api_key=config.PERPLEXITY_API_KEY)
    ghost_client = GhostClient(
        ghost_url=config.GHOST_URL,
        admin_api_key=config.GHOST_ADMIN_API_KEY
    )

    # Initialize service
    service = DigestService(
        leviathan_client=leviathan_client,
        perplexity_client=perplexity_client,
        ghost_client=ghost_client
    )

    # Generate digest
    click.echo("Generating digest with Perplexity AI...")
    digest_content = service.generate_digest(items)
    click.secho("✓ Digest generated", fg="green")

    # Publish unless dry run
    if not dry_run:
        click.echo("Publishing to Ghost...")
        service.publish_digest(digest_content)
        click.secho("✓ Published to Ghost", fg="green")

    return digest_content


def _display_dry_run_output(content):
    """Display digest content for dry runs."""
    click.secho("\n" + "=" * 80, fg="yellow")
    click.secho("DRY RUN - Digest generated but not published", fg="yellow")
    click.secho("=" * 80 + "\n", fg="yellow")
    click.echo(content)
    click.echo("\n" + "=" * 80 + "\n")


def _get_test_data():
    """Return test data for development without API calls."""
    return [
        {
            "headline": "Ambitious Yearn dev shares one neat trick that made him $40 from ChatGPT",
            "source": "𝕏/@MarcoWorms",
            "url": "https://leviathannews.xyz/redirect/17755",
            "tags": [{"name": "ChatGPT"}, {"name": "Yearn"}, {"name": "Web3 Development"}]
        },
        {
            "headline": "The ECB is winning support for a ban on stablecoins issued jointly in the bloc and other jurisdictions",
            "source": "archive.ph",
            "url": "https://leviathannews.xyz/redirect/17814",
            "tags": [{"name": "Stablecoins"}, {"name": "ECB"}, {"name": "ESRB"}]
        },
        {
            "headline": "JPMorgan Chase is rolling out agentic AI to automate complex tasks, part of its push to become the first fully AI-powered megabank",
            "source": "CNBC",
            "url": "https://leviathannews.xyz/redirect/17830",
            "tags": [{"name": "AI"}, {"name": "JPMorgan Chase"}, {"name": "investment"}]
        }
    ]


if __name__ == "__main__":
    main()
