"""Client for Ghost CMS API."""
import httpx
from typing import List, Optional


class GhostClient:
    """Publishes content to Ghost CMS."""

    def __init__(self, ghost_url: str, admin_api_key: str, timeout: int = 30):
        self.ghost_url = ghost_url.rstrip('/')
        self.admin_api_key = admin_api_key
        self.timeout = timeout

    def create_post(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        status: str = "published",
        meta_description: Optional[str] = None
    ) -> dict:
        """
        Create a new post in Ghost.

        Args:
            title: Post title
            content: Post content (HTML or markdown)
            tags: List of tag names
            status: Post status ("published", "draft", etc.)
            meta_description: SEO meta description

        Returns:
            Created post data from Ghost API

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        tags = tags or []

        # Convert plain text to HTML paragraphs
        html_content = f"<p>{content.replace(chr(10), '</p><p>')}</p>"

        post_data = {
            "posts": [{
                "title": title,
                "html": html_content,
                "status": status,
                "tags": tags,
                "meta_title": title,
                "meta_description": meta_description or title
            }]
        }

        headers = {
            "Authorization": f"Ghost {self.admin_api_key}",
            "Content-Type": "application/json"
        }

        url = f"{self.ghost_url}/ghost/api/admin/posts/"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=post_data)
            response.raise_for_status()
            return response.json()
