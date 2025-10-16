"""Ghost email client for Squid Digest."""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import httpx
import markdown2
from .templates import admin_notification_template, public_digest_template, edit_notification_template


class GhostEmailClient:
    """Client for sending emails via Ghost Admin API."""
    
    def __init__(self, ghost_url: Optional[str] = None, admin_api_key: Optional[str] = None):
        """Initialize Ghost email client.
        
        Args:
            ghost_url: Ghost site URL. If None, will read from GHOST_URL env var.
            admin_api_key: Ghost Admin API key. If None, will read from GHOST_ADMIN_API_KEY env var.
        """
        self.ghost_url = ghost_url or os.getenv("GHOST_URL")
        self.admin_api_key = admin_api_key or os.getenv("GHOST_ADMIN_API_KEY")
        
        if not self.ghost_url:
            raise ValueError("Ghost URL is required. Set GHOST_URL environment variable.")
        if not self.admin_api_key:
            raise ValueError("Ghost Admin API key is required. Set GHOST_ADMIN_API_KEY environment variable.")
        
        # Clean up URL
        self.ghost_url = self.ghost_url.rstrip('/')
        self.api_url = f"{self.ghost_url}/ghost/api/admin"
        
        # Email configuration
        self.from_email = os.getenv("GHOST_FROM_EMAIL", "noreply@ghost.local")
        self.from_name = os.getenv("GHOST_FROM_NAME", "Squid Digest")
        
    def _get_headers(self) -> dict:
        """Get headers for Ghost API requests."""
        return {
            "Authorization": f"Ghost {self.admin_api_key}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make API request to Ghost."""
        url = f"{self.api_url}/{endpoint}"
        
        try:
            with httpx.Client() as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    json=data,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"Ghost API request failed: {e}")
            raise
    
    def get_members(self, filter_query: str = None) -> List[Dict[str, Any]]:
        """Get members from Ghost.
        
        Args:
            filter_query: Ghost filter query (e.g., "label:admin")
            
        Returns:
            List of member objects
        """
        endpoint = "members"
        if filter_query:
            endpoint += f"?filter={filter_query}"
        
        response = self._make_request("GET", endpoint)
        return response.get("members", [])
    
    def create_member(self, email: str, name: str = None, labels: List[str] = None) -> Dict[str, Any]:
        """Create a new member in Ghost.
        
        Args:
            email: Member email address
            name: Member name (optional)
            labels: List of labels to assign (optional)
            
        Returns:
            Created member object
        """
        member_data = {
            "members": [{
                "email": email,
                "name": name or email.split("@")[0],
                "labels": labels or []
            }]
        }
        
        response = self._make_request("POST", "members", member_data)
        return response.get("members", [{}])[0]
    
    def ensure_member_exists(self, email: str, labels: List[str] = None) -> Dict[str, Any]:
        """Ensure a member exists, create if not.
        
        Args:
            email: Member email address
            labels: List of labels to assign
            
        Returns:
            Member object
        """
        # Check if member exists
        existing_members = self.get_members(f"email:{email}")
        
        if existing_members:
            member = existing_members[0]
            # Update labels if provided
            if labels:
                current_labels = [label.get("name") for label in member.get("labels", [])]
                new_labels = list(set(current_labels + labels))
                if new_labels != current_labels:
                    self.update_member_labels(member["id"], new_labels)
            return member
        else:
            # Create new member
            return self.create_member(email, labels=labels)
    
    def update_member_labels(self, member_id: str, labels: List[str]) -> Dict[str, Any]:
        """Update member labels.
        
        Args:
            member_id: Ghost member ID
            labels: List of label names
            
        Returns:
            Updated member object
        """
        member_data = {
            "members": [{
                "id": member_id,
                "labels": labels
            }]
        }
        
        response = self._make_request("PUT", f"members/{member_id}", member_data)
        return response.get("members", [{}])[0]
    
    def create_post(self, title: str, html_content: str, status: str = "draft") -> Dict[str, Any]:
        """Create a post in Ghost.
        
        Args:
            title: Post title
            html_content: HTML content
            status: Post status (draft, published)
            
        Returns:
            Created post object
        """
        post_data = {
            "posts": [{
                "title": title,
                "html": html_content,
                "status": status,
                "tags": ["digest", "automated"]  # Add tags for organization
            }]
        }
        
        response = self._make_request("POST", "posts", post_data)
        return response.get("posts", [{}])[0]
    
    def send_email_to_members(self, post_id: str, member_filter: str = None) -> bool:
        """Send email to members using Ghost's email system.
        
        Args:
            post_id: Ghost post ID
            member_filter: Filter for which members to send to (e.g., "label:admin")
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Ghost doesn't have a direct API for sending emails to specific members
            # Instead, we'll use the post publishing with email feature
            # This requires the post to be published with email delivery
            
            # Update post to be published and set email delivery
            post_data = {
                "posts": [{
                    "id": post_id,
                    "status": "published",
                    "email_recipient_filter": member_filter or "all"
                }]
            }
            
            response = self._make_request("PUT", f"posts/{post_id}", post_data)
            return True
            
        except Exception as e:
            print(f"Failed to send email via Ghost: {e}")
            return False
    
    def format_digest_html(self, markdown_content: str) -> str:
        """Convert markdown digest content to HTML.
        
        Args:
            markdown_content: Raw markdown content
            
        Returns:
            HTML formatted content
        """
        # Convert markdown to HTML
        html_content = markdown2.markdown(
            markdown_content,
            extras=[
                'fenced-code-blocks',
                'tables',
                'header-ids',
                'link-patterns'
            ]
        )
        
        return html_content
    
    def send_admin_notification(self, digest_path: str, github_url: str, is_edit: bool = False) -> bool:
        """Send notification email to admins via Ghost.
        
        Args:
            digest_path: Path to the digest file
            github_url: GitHub URL to the digest file
            is_edit: Whether this is an edit notification
            
        Returns:
            True if email sent successfully, False otherwise
        """
        admin_emails = os.getenv("ADMIN_EMAILS", "ghall1@gmail.com").split(",")
        admin_emails = [email.strip() for email in admin_emails if email.strip()]
        
        if not admin_emails:
            print("No admin emails configured")
            return False
        
        # Ensure admin members exist with admin label
        for email in admin_emails:
            self.ensure_member_exists(email, labels=["admin"])
        
        # Generate HTML content
        html_content = admin_notification_template(digest_path, github_url, is_edit)
        
        # Replace timestamp placeholder
        html_content = html_content.replace("{{ timestamp }}", datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"))
        
        # Determine title
        if is_edit:
            title = "✏️ Digest Draft Edited - Review Required"
        else:
            title = "🔍 Daily Digest Draft Ready for Review"
        
        # Create post in Ghost
        post = self.create_post(title, html_content, status="draft")
        
        # Send email to admin members
        return self.send_email_to_members(post["id"], "label:admin")
    
    def send_digest_email(self, digest_path: str, recipients: Optional[List[str]] = None) -> bool:
        """Send digest email to public recipients via Ghost.
        
        Args:
            digest_path: Path to the digest markdown file
            recipients: List of recipient emails. If None, uses PUBLIC_EMAILS env var.
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if recipients is None:
            public_emails = os.getenv("PUBLIC_EMAILS", "ghall1@gmail.com,curvedefi@gmail.com").split(",")
            recipients = [email.strip() for email in public_emails if email.strip()]
        
        if not recipients:
            print("No public emails configured")
            return False
        
        # Ensure public members exist with subscriber label
        for email in recipients:
            self.ensure_member_exists(email, labels=["subscriber"])
        
        # Read digest content
        digest_file = Path(digest_path)
        if not digest_file.exists():
            print(f"Digest file not found: {digest_path}")
            return False
        
        with open(digest_file, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # Extract date from filename or content
        date_str = datetime.now().strftime("%B %d, %Y")
        if "trading_signals_" in digest_file.name:
            try:
                date_part = digest_file.stem.split("_")[-1]  # Get date part
                parsed_date = datetime.strptime(date_part, "%Y-%m-%d")
                date_str = parsed_date.strftime("%B %d, %Y")
            except:
                pass  # Use current date if parsing fails
        
        # Convert to HTML
        html_digest_content = self.format_digest_html(markdown_content)
        
        # Generate full email HTML
        html_content = public_digest_template(html_digest_content, date_str)
        
        # Generate title
        title = f"📊 Crypto Trading Signals - {date_str}"
        
        # Create post in Ghost
        post = self.create_post(title, html_content, status="draft")
        
        # Send email to subscriber members
        return self.send_email_to_members(post["id"], "label:subscriber")
    
    def send_edit_notification(self, digest_path: str, github_url: str, changes_summary: str = "") -> bool:
        """Send edit notification email to admins via Ghost.
        
        Args:
            digest_path: Path to the digest file
            github_url: GitHub URL to the digest file
            changes_summary: Summary of changes made
            
        Returns:
            True if email sent successfully, False otherwise
        """
        admin_emails = os.getenv("ADMIN_EMAILS", "ghall1@gmail.com").split(",")
        admin_emails = [email.strip() for email in admin_emails if email.strip()]
        
        if not admin_emails:
            print("No admin emails configured")
            return False
        
        # Ensure admin members exist with admin label
        for email in admin_emails:
            self.ensure_member_exists(email, labels=["admin"])
        
        # Generate HTML content
        html_content = edit_notification_template(digest_path, github_url, changes_summary)
        
        # Replace timestamp placeholder
        html_content = html_content.replace("{{ timestamp }}", datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"))
        
        title = "✏️ Digest Draft Edited - Review Required"
        
        # Create post in Ghost
        post = self.create_post(title, html_content, status="draft")
        
        # Send email to admin members
        return self.send_email_to_members(post["id"], "label:admin")
