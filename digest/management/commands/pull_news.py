import sys
from django.core.management.base import BaseCommand
from django.conf import settings

from digest.clients import LeviathanNewsClient, PerplexityClient, GhostClient
from digest.services import DigestService


class Command(BaseCommand):
    help = "Pull news from Leviathan API, generate digest with Perplexity, and send via Ghost"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10, help="Number of news items to process")
        parser.add_argument("--dry-run", action="store_true", help="Generate digest but don't send to Ghost")
        parser.add_argument("--test", action="store_true", help="Use test data instead of API call")

    def handle(self, *args, **opts):
        """
        Main entry point for the pull_news command.

        Flow:
        1. Get news items (from API or test data)
        2. Generate digest with Perplexity AI
        3. Publish to Ghost (unless --dry-run)
        """
        try:
            # Get news items
            if opts["test"]:
                items = self._get_test_data()
                self.stdout.write(self.style.SUCCESS(f"Using {len(items)} test news items"))
            else:
                items = self._fetch_news(opts["limit"])

            if not items:
                self.stdout.write(self.style.WARNING("No news items to process"))
                return

            # Generate and optionally publish digest
            digest_content = self._run_digest_pipeline(items, opts["dry_run"])

            # Output results
            if opts["dry_run"]:
                self._display_dry_run_output(digest_content)
            else:
                self.stdout.write(self.style.SUCCESS("✓ Digest sent to Ghost successfully!"))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Pipeline failed: {e}"))
            sys.exit(1)

    def _fetch_news(self, limit: int):
        """Fetch news using LeviathanNewsClient."""
        try:
            client = LeviathanNewsClient()
            items = client.fetch_top_news(limit=limit)
            self.stdout.write(self.style.SUCCESS(f"✓ Fetched {len(items)} news items"))
            return items
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch news: {e}"))
            return []

    def _run_digest_pipeline(self, items, dry_run: bool):
        """Run the digest generation and publishing pipeline."""
        # Initialize clients
        leviathan_client = LeviathanNewsClient()
        perplexity_client = PerplexityClient(api_key=settings.PERPLEXITY_API_KEY)
        ghost_client = GhostClient(
            ghost_url=settings.GHOST_URL,
            admin_api_key=settings.GHOST_ADMIN_API_KEY
        )

        # Initialize service
        service = DigestService(
            leviathan_client=leviathan_client,
            perplexity_client=perplexity_client,
            ghost_client=ghost_client
        )

        # Generate digest
        self.stdout.write("Generating digest with Perplexity AI...")
        digest_content = service.generate_digest(items)
        self.stdout.write(self.style.SUCCESS("✓ Digest generated"))

        # Publish unless dry run
        if not dry_run:
            self.stdout.write("Publishing to Ghost...")
            service.publish_digest(digest_content)
            self.stdout.write(self.style.SUCCESS("✓ Published to Ghost"))

        return digest_content

    def _display_dry_run_output(self, content):
        """Display digest content for dry runs."""
        self.stdout.write(self.style.WARNING("\n" + "="*80))
        self.stdout.write(self.style.WARNING("DRY RUN - Digest generated but not published"))
        self.stdout.write(self.style.WARNING("="*80 + "\n"))
        self.stdout.write(content)
        self.stdout.write("\n" + "="*80 + "\n")

    def _get_test_data(self):
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
