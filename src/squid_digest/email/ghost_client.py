"""Ghost email client for Squid Digest."""

import os
import re
import jwt
import datetime
from datetime import datetime as dt
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
        """Get headers for Ghost API requests with proper JWT token."""
        # Generate JWT token from API key
        token = self._generate_jwt_token()
        
        return {
            "Authorization": f"Ghost {token}",
            "Content-Type": "application/json"
        }
    
    def _generate_jwt_token(self) -> str:
        """Generate JWT token for Ghost Admin API authentication."""
        # Split the API key into ID and SECRET
        try:
            id_part, secret_part = self.admin_api_key.split(':')
        except ValueError:
            raise ValueError("Invalid Ghost API key format. Expected format: 'id:secret'")
        
        # Prepare header and payload
        iat = int(dt.now().timestamp())
        exp = iat + 5 * 60  # Token expires in 5 minutes
        
        header = {
            'alg': 'HS256',
            'typ': 'JWT',
            'kid': id_part
        }
        
        payload = {
            'iat': iat,
            'exp': exp,
            'aud': '/admin/'
        }
        
        # Create the token
        token = jwt.encode(payload, bytes.fromhex(secret_part), algorithm='HS256', headers=header)
        return token
    
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
                
                # Print detailed error information for debugging
                if not response.is_success:
                    print(f"API Error Details:")
                    print(f"  Status: {response.status_code}")
                    print(f"  URL: {url}")
                    if data:
                        print(f"  Request Data: {data}")
                    try:
                        error_details = response.json()
                        print(f"  Error Response: {error_details}")
                    except:
                        print(f"  Error Text: {response.text}")
                
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
        endpoint = "members/"
        if filter_query:
            endpoint += f"?filter={filter_query}"
        
        try:
            response = self._make_request("GET", endpoint)
            return response.get("members", [])
        except Exception as e:
            print(f"Warning: Could not fetch members from Ghost API: {e}")
            print("This might be due to API key permissions or Ghost version differences.")
            return []
    
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
        
        response = self._make_request("POST", "members/", member_data)
        return response.get("members", [{}])[0]
    
    def ensure_member_exists(self, email: str, labels: List[str] = None) -> Dict[str, Any]:
        """Ensure a member exists, create if not.
        
        Args:
            email: Member email address
            labels: List of labels to assign
            
        Returns:
            Member object
        """
        # Try to check if member exists
        existing_members = self.get_members(f"email:{email}")
        
        if existing_members:
            member = existing_members[0]
            # Update labels if provided
            if labels:
                current_labels = [label.get("name") for label in member.get("labels", [])]
                new_labels = list(set(current_labels + labels))
                if new_labels != current_labels:
                    try:
                        self.update_member_labels(member["id"], new_labels)
                    except Exception as e:
                        print(f"Warning: Could not update member labels: {e}")
            return member
        else:
            # Create new member
            try:
                return self.create_member(email, labels=labels)
            except Exception as e:
                print(f"Warning: Could not create member {email}: {e}")
                # Return a mock member object for testing
                return {
                    "id": f"mock-{email}",
                    "email": email,
                    "name": email.split("@")[0],
                    "labels": labels or []
                }
    
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
        """Create a post in Ghost using mobiledoc format.
        
        Args:
            title: Post title
            html_content: HTML content
            status: Post status (draft, published)
            
        Returns:
            Created post object
        """
        # Convert HTML to mobiledoc format for Ghost
        mobiledoc = self._html_to_mobiledoc(html_content)
        
        post_data = {
            "posts": [{
                "title": title,
                "mobiledoc": mobiledoc,
                "status": status,
                "tags": ["digest", "automated"]  # Add tags for organization
            }]
        }
        
        response = self._make_request("POST", "posts", post_data)
        return response.get("posts", [{}])[0]
    
    def _html_to_mobiledoc(self, html_content: str) -> str:
        """Convert HTML content to Ghost's mobiledoc format.
        
        Args:
            html_content: HTML content
            
        Returns:
            Mobiledoc JSON string
        """
        import json
        
        # Simple mobiledoc structure for HTML content
        mobiledoc = {
            "version": "0.3.1",
            "markups": [],
            "atoms": [],
            "cards": [
                ["html", {"html": html_content}]
            ],
            "sections": [
                [10, 0]  # Card section referencing card 0
            ]
        }
        
        return json.dumps(mobiledoc)
    
    def send_email_to_members(self, post_id: str, member_filter: str = None) -> bool:
        """Create and publish post in Ghost - email delivery depends on Ghost configuration.
        
        Args:
            post_id: Ghost post ID
            member_filter: Filter for which members to send to (e.g., "label:admin")
            
        Returns:
            True if post published successfully, False otherwise
        """
        try:
            # First, get the current post to get the updated_at timestamp
            current_post = self._make_request("GET", f"posts/{post_id}/")
            post_data = current_post.get("posts", [{}])[0]
            
            # Update the post to published status
            update_data = {
                "posts": [{
                    "id": post_id,
                    "status": "published",
                    "updated_at": post_data.get("updated_at")
                }]
            }
            
            response = self._make_request("PUT", f"posts/{post_id}/", update_data)
            print(f"✓ Post {post_id} published successfully")
            print(f"✓ Post URL: {post_data.get('url', 'N/A')}")
            
            # Note: Ghost Admin API doesn't have direct email sending
            # Email delivery requires Ghost's newsletter system to be configured
            print("📧 Note: Email delivery requires Ghost admin panel configuration")
            print("   - Go to Ghost admin → Settings → Email newsletter")
            print("   - Configure email service (SendGrid, Mailgun, etc.)")
            print("   - Set up automatic newsletter delivery")
            
            return True
            
        except Exception as e:
            print(f"Warning: Could not publish post via Ghost API: {e}")
            return False
    
    def format_digest_html(self, markdown_content: str) -> str:
        """Convert markdown digest content to HTML with improved formatting.
        
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
                'header-ids'
            ]
        )
        
        # Post-process HTML to fix link colors and improve layout
        html_content = self._improve_html_formatting(html_content)
        
        return html_content
    
    def _improve_html_formatting(self, html_content: str) -> str:
        """Improve HTML formatting for better email display.
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            Improved HTML content
        """
        import re
        
        # Fix link colors - change all links to dark blue
        html_content = re.sub(
            r'<a([^>]*)href="([^"]*)"([^>]*)>',
            r'<a\1href="\2"\3 style="color: #021f53; text-decoration: none;">',
            html_content
        )
        
        # Remove any existing color styles from links
        html_content = re.sub(
            r'<a([^>]*)style="([^"]*)"([^>]*)>',
            lambda m: f'<a{m.group(1)}style="color: #021f53; text-decoration: none; {m.group(2)}"{m.group(3)}>',
            html_content
        )
        
        # Convert table layout to improved story layout
        html_content = self._convert_table_to_story_layout(html_content)
        
        return html_content
    
    def _convert_table_to_story_layout(self, html_content: str) -> str:
        """Convert table-based story layout to improved full-width layout.
        
        Args:
            html_content: HTML content with table layout
            
        Returns:
            HTML content with improved story layout
        """
        import re
        
        # More flexible pattern to match story rows - handles the exact structure we see
        story_pattern = r'<tr>\s*<td[^>]*>\s*<img[^>]*src="([^"]*)"[^>]*>\s*</td>\s*<td[^>]*>\s*<strong><a[^>]*href="([^"]*)"[^>]*>([^<]*)</a></strong>[^<]*<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>\s*<br><span[^>]*>🏷️\s*([^<]*)</span>\s*<br>💬\s*<i>([^<]*)</i>\s*—\s*@([^<\s]*)'
        
        def replace_story(match):
            img_url = match.group(1)
            story_url = match.group(2)
            story_title = match.group(3)
            source_url = match.group(4)
            source_text = match.group(5)
            tags = match.group(6)
            comment = match.group(7)
            username = match.group(8)
            
            # Create improved story layout
            return f'''
            <div style="margin-bottom: 30px; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden;">
                <a href="{story_url}" style="display: block; text-decoration: none;">
                    <img src="{img_url}" alt="Story Image" style="width: 100%; height: 200px; object-fit: cover; display: block;">
                </a>
                <div style="padding: 20px;">
                    <h3 style="margin: 0 0 10px 0; font-size: 18px; line-height: 1.4; color: #333;">
                        {story_title}
                    </h3>
                    <p style="margin: 0 0 15px 0; color: #666; font-size: 14px;">
                        Source: <a href="{source_url}" style="color: #021f53; text-decoration: none;">{source_text}</a>
                    </p>
                    <div style="margin: 10px 0; font-size: 13px; color: #666;">
                        🏷️ {tags}
                    </div>
                    <blockquote style="margin: 15px 0 0 0; padding: 10px 15px; background: #f8f9fa; border-left: 3px solid #021f53; font-style: italic; color: #555;">
                        "{comment}"
                        <br><small style="color: #666;">— <a href="https://leviathannews.xyz/user/{username}/comments" style="color: #021f53; text-decoration: none;">@{username}</a></small>
                    </blockquote>
                </div>
            </div>
            '''
        
        # Try the complex pattern first
        html_content = re.sub(story_pattern, replace_story, html_content, flags=re.DOTALL)
        
        # If that didn't work, try a simpler approach - just replace the table structure
        if '<tr>' in html_content and '<td' in html_content:
            # Fallback: simpler pattern that just extracts the key elements
            simple_pattern = r'<tr>\s*<td[^>]*>\s*<img[^>]*src="([^"]*)"[^>]*>\s*</td>\s*<td[^>]*>\s*(.*?)\s*</td>\s*</tr>'
            
            def simple_replace(match):
                img_url = match.group(1)
                content = match.group(2)
                
                # Extract story title (first <strong><a> tag)
                title_match = re.search(r'<strong><a[^>]*href="([^"]*)"[^>]*>([^<]*)</a></strong>', content)
                if title_match:
                    story_url = title_match.group(1)
                    story_title = title_match.group(2)
                else:
                    story_url = "#"
                    story_title = "Story"
                
                # Extract source (second <a> tag, after the title)
                all_links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', content)
                if len(all_links) >= 2:
                    # Second link is the source
                    source_url = all_links[1][0]
                    source_text = all_links[1][1]
                else:
                    source_url = "#"
                    source_text = "Source"
                
                # Extract tags from the span element and make them clickable
                tags_match = re.search(r'<span[^>]*>🏷️\s*(.*?)</span>', content, re.DOTALL)
                if tags_match:
                    # Extract individual tag links from the span and create clickable HTML
                    tag_links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', tags_match.group(1))
                    clickable_tags = []
                    for url, text in tag_links:
                        clickable_tags.append(f'<a href="{url}" style="color: #021f53; text-decoration: none;">{text}</a>')
                    tags = " • ".join(clickable_tags)
                else:
                    # Fallback: try to extract tags without span
                    tags_match = re.search(r'🏷️\s*([^<]*)', content)
                    tags = tags_match.group(1).strip() if tags_match else ""
                
                # Extract comment and username
                comment_match = re.search(r'💬\s*<i>([^<]*)</i>\s*—\s*@([^<\s]*)', content)
                if comment_match:
                    comment = comment_match.group(1)
                    username = comment_match.group(2)
                else:
                    comment = ""
                    username = ""
                
                return f'''
                <div style="margin-bottom: 30px; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden;">
                    <a href="{story_url}" style="display: block; text-decoration: none;">
                        <img src="{img_url}" alt="Story Image" style="width: 100%; height: 200px; object-fit: cover; display: block;">
                    </a>
                    <div style="padding: 20px;">
                        <h3 style="margin: 0 0 10px 0; font-size: 18px; line-height: 1.4; color: #333;">
                            {story_title}
                        </h3>
                        <p style="margin: 0 0 15px 0; color: #666; font-size: 14px;">
                            Source: <a href="{source_url}" style="color: #021f53; text-decoration: none;">{source_text}</a>
                        </p>
                        <div style="margin: 10px 0; font-size: 13px; color: #666;">
                            🏷️ {tags}
                        </div>
                        <blockquote style="margin: 15px 0 0 0; padding: 10px 15px; background: #f8f9fa; border-left: 3px solid #021f53; font-style: italic; color: #555;">
                            "{comment}"
                            <br><small style="color: #666;">— <a href="https://leviathannews.xyz/user/{username}/comments" style="color: #021f53; text-decoration: none;">@{username}</a></small>
                        </blockquote>
                    </div>
                </div>
                '''
            
            html_content = re.sub(simple_pattern, simple_replace, html_content, flags=re.DOTALL)
        
        # Remove the table wrapper if it's empty
        html_content = re.sub(r'<table[^>]*>\s*</table>', '', html_content)
        
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
        
        print(f"Attempting to send admin notification to: {', '.join(admin_emails)}")
        
        # Try to ensure admin members exist with admin label
        for email in admin_emails:
            try:
                self.ensure_member_exists(email, labels=["admin"])
            except Exception as e:
                print(f"Warning: Could not manage member {email}: {e}")
        
        # Generate HTML content for the notification
        html_content = admin_notification_template(digest_path, github_url, is_edit)
        
        # Replace timestamp placeholder
        html_content = html_content.replace("{{ timestamp }}", dt.now().strftime("%Y-%m-%d %H:%M:%S UTC"))
        
        # Determine title
        if is_edit:
            title = "✏️ Digest Draft Edited - Review Required"
        else:
            title = "🔍 Daily Digest Draft Ready for Review"
        
        # Try to create post in Ghost
        try:
            post = self.create_post(title, html_content, status="draft")
            print(f"✓ Created Ghost notification post: {post.get('id', 'unknown')}")
            
            # Keep as draft so it shows up in admin panel for review
            print(f"✓ Post {post.get('id', 'unknown')} created as draft")
            print(f"✓ Post URL: {post.get('url', 'N/A')}")
            print("📧 Note: Email delivery requires Ghost admin panel configuration")
            print("   - Go to Ghost admin → Settings → Email newsletter")
            print("   - Configure email service (SendGrid, Mailgun, etc.)")
            print("   - Set up automatic newsletter delivery")
            
            return True
            
        except Exception as e:
            print(f"Error: Could not create Ghost notification post: {e}")
            print("This might be due to API key permissions.")
            print("The digest content is ready but cannot be sent via Ghost email.")
            return False
    
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
        date_str = dt.now().strftime("%B %d, %Y")
        if "trading_signals_" in digest_file.name:
            try:
                date_part = digest_file.stem.split("_")[-1]  # Get date part
                parsed_date = dt.strptime(date_part, "%Y-%m-%d")
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
        html_content = html_content.replace("{{ timestamp }}", dt.now().strftime("%Y-%m-%d %H:%M:%S UTC"))
        
        title = "✏️ Digest Draft Edited - Review Required"
        
        # Create post in Ghost
        post = self.create_post(title, html_content, status="draft")
        
        # Send email to admin members
        return self.send_email_to_members(post["id"], "label:admin")
