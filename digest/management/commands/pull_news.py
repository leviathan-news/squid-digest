import os
import sys
import json
import httpx
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = "Pull news from Leviathan API, generate digest with Perplexity, and send via Ghost"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10, help="Number of news items to process")
        parser.add_argument("--dry-run", action="store_true", help="Generate digest but don't send to Ghost")
        parser.add_argument("--test", action="store_true", help="Use test data instead of API call")

    def handle(self, *args, **opts):
        # Get news items
        if opts["test"]:
            items = self._get_test_data()
        else:
            items = self._fetch_news_items(opts["limit"])
        
        if not items:
            self.stdout.write(self.style.WARNING("No news items to process"))
            return

        # Generate digest with Perplexity
        digest_content = self._generate_digest_with_perplexity(items)
        if not digest_content:
            self.stderr.write(self.style.ERROR("Failed to generate digest"))
            sys.exit(1)

        # Send to Ghost (unless dry run)
        if not opts["dry_run"]:
            success = self._send_to_ghost(digest_content)
            if success:
                self.stdout.write(self.style.SUCCESS("Digest sent to Ghost successfully!"))
            else:
                self.stderr.write(self.style.ERROR("Failed to send digest to Ghost"))
                sys.exit(1)
        else:
            self.stdout.write(self.style.WARNING("DRY RUN - Digest generated but not sent:"))
            self.stdout.write("\n" + "="*80 + "\n")
            self.stdout.write(digest_content)
            self.stdout.write("\n" + "="*80 + "\n")

    def _fetch_news_items(self, limit):
        """Fetch news items from Leviathan API"""
        url = "https://api.leviathannews.xyz/api/v1/news/?sort_type=hot&sort_timeframe=1"
        
        try:
            with httpx.Client(timeout=20) as client:
                r = client.get(url, params={"limit": limit})
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to fetch news: {e}"))
            return []

        items = data if isinstance(data, list) else data.get("results") or data.get("items") or []
        self.stdout.write(self.style.SUCCESS(f"Fetched {len(items)} news items"))
        return items

    def _get_test_data(self):
        """Return test data for development"""
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

    def _generate_digest_with_perplexity(self, items):
        """Generate digest using Perplexity API"""
        if not settings.PERPLEXITY_API_KEY:
            self.stderr.write(self.style.ERROR("PERPLEXITY_API_KEY not configured"))
            return None

        # Prepare headlines for the prompt
        headlines_text = "\n".join([
            f"• {item.get('headline', 'No headline')} (Source: {item.get('source', 'Unknown')})"
            for item in items
        ])

        prompt = f"""You are a crypto and tech news analyst creating a daily digest. Based on these top headlines from Leviathan News, create a compelling daily digest that:

1. **Summarizes the key themes** across all stories
2. **Explains the significance** of each major story in 2-3 sentences
3. **Identifies trends** and patterns in the news
4. **Provides context** about why these stories matter to crypto/tech audiences
5. **Writes in an engaging, newsletter-style tone** that's informative but accessible

Today's Top Headlines:
{headlines_text}

Format your response as a newsletter digest with:
- A compelling subject line
- Brief intro paragraph
- 3-4 main story summaries with analysis
- A closing section highlighting key trends
- Keep it concise but insightful (aim for 300-500 words total)

Make it engaging and valuable for crypto/tech professionals who want to stay informed but don't have time to read everything."""

        try:
            # Use httpx directly for Perplexity API
            headers = {
                "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "sonar-reasoning-pro",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert crypto and tech news analyst who creates engaging daily digests."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 1000
            }
            
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
            
            digest = data["choices"][0]["message"]["content"]
            self.stdout.write(self.style.SUCCESS("Digest generated with Perplexity"))
            return digest
            
        except httpx.HTTPStatusError as e:
            self.stderr.write(self.style.ERROR(f"Perplexity API HTTP error: {e}"))
            self.stderr.write(self.style.ERROR(f"Response: {e.response.text}"))
            return None
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Perplexity API error: {e}"))
            return None

    def _send_to_ghost(self, content):
        """Send digest to Ghost as a post"""
        if not all([settings.GHOST_URL, settings.GHOST_ADMIN_API_KEY]):
            self.stderr.write(self.style.ERROR("Ghost configuration missing"))
            return False

        # Extract subject line and body from content
        lines = content.strip().split('\n')
        subject_line = lines[0] if lines else "Daily Crypto & Tech Digest"
        body_content = '\n'.join(lines[1:]) if len(lines) > 1 else content

        post_data = {
            "posts": [{
                "title": subject_line,
                "html": f"<p>{body_content.replace(chr(10), '</p><p>')}</p>",
                "status": "published",
                "tags": ["digest", "crypto", "tech", "news"],
                "meta_title": subject_line,
                "meta_description": "Daily digest of top crypto and tech news from Leviathan News"
            }]
        }

        try:
            headers = {
                "Authorization": f"Ghost {settings.GHOST_ADMIN_API_KEY}",
                "Content-Type": "application/json"
            }
            
            with httpx.Client(timeout=30) as client:
                r = client.post(
                    f"{settings.GHOST_URL}/ghost/api/admin/posts/",
                    headers=headers,
                    json=post_data
                )
                r.raise_for_status()
                
            self.stdout.write(self.style.SUCCESS("Post created in Ghost"))
            return True
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Ghost API error: {e}"))
            return False
