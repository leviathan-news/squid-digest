import os
import sys
import httpx
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Pull a simple daily digest from Leviathan News API"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10, help="Number of items")

    def handle(self, *args, **opts):
        url = "https://api.leviathannews.xyz/api/v1/news/?sort_type=hot&sort_timeframe=7"
        token = None
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            with httpx.Client(timeout=20) as client:
                r = client.get(url, params={"limit": opts["limit"]}, headers=headers)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Request failed: {e}"))
            sys.exit(2)

        items = data if isinstance(data, list) else data.get("results") or data.get("items") or []
        if not items:
            self.stdout.write(self.style.WARNING("No items returned"))
            return

        self.stdout.write(self.style.SUCCESS(f"Top {min(len(items), opts['limit'])} headlines:\n"))
        for i, it in enumerate(items[:opts["limit"]], 1):
            title = it.get("title") or it.get("headline") or "(no title)"
            link = it.get("url") or it.get("link") or ""
            self.stdout.write(f"{i}. {title}\n   {link}")

