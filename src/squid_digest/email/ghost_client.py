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

        # Set by send_email_to_members after a successful publish
        self.last_published_url = None
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
    
    def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None, params: Dict[str, str] = None) -> Dict[str, Any]:
        """Make API request to Ghost.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data (for POST/PUT)
            params: Query parameters to append to URL
        """
        url = f"{self.api_url}/{endpoint}"

        try:
            with httpx.Client() as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    json=data,
                    params=params,
                    timeout=30
                )

                # Print detailed error information for debugging
                if not response.is_success:
                    print(f"API Error Details:")
                    print(f"  Status: {response.status_code}")
                    print(f"  URL: {response.url}")
                    if params:
                        print(f"  Query Params: {params}")
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
    
    def create_post(self, title: str, html_content: str, status: str = "draft", send_email: bool = False) -> Dict[str, Any]:
        """Create a post in Ghost using mobiledoc format.
        
        Args:
            title: Post title
            html_content: HTML content
            status: Post status (draft, published)
            send_email: If True and status is published, send email to subscribers
            
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
        
        # If sending email, add email settings
        if send_email and status == "published":
            # Try to get newsletter ID for email recipient filter
            try:
                newsletters = self._make_request("GET", "newsletters/")
                if newsletters.get("newsletters"):
                    newsletter_id = newsletters["newsletters"][0].get("id")
                    # Use email_recipient_filter to send to newsletter subscribers
                    # Note: This tells Ghost WHO to send to, but Ghost may require
                    # manual "Send email" action from admin panel for some versions
                    post_data["posts"][0]["email_recipient_filter"] = f"newsletters:{newsletter_id}"
                    print(f"✓ Set email_recipient_filter to newsletter: {newsletter_id}")
            except Exception as e:
                print(f"Warning: Could not set email recipient filter: {e}")
        
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
        """Send email to members via Ghost newsletter API.

        Uses the correct Ghost API method: publishing a post with newsletter query parameters.

        Args:
            post_id: Ghost post ID
            member_filter: Filter for which members to send to (e.g., "label:subscriber")

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Get the current post
            current_post = self._make_request("GET", f"posts/{post_id}/")
            post_data = current_post.get("posts", [{}])[0]

            # Get newsletter information
            newsletters = self._make_request("GET", "newsletters/")
            newsletter_list = newsletters.get("newsletters", [])

            if not newsletter_list:
                print("⚠️  No newsletters found in Ghost")
                print("📧 Please configure a newsletter in Ghost admin panel: Settings → Email newsletter")
                return False

            # Use the first (default) newsletter
            newsletter = newsletter_list[0]
            newsletter_slug = newsletter.get("slug", "default-newsletter")
            newsletter_name = newsletter.get("name", "Newsletter")

            print(f"📧 Using newsletter: {newsletter_name} (slug: {newsletter_slug})")

            # Prepare the publish update with newsletter query parameters
            # This is the correct way to trigger email sending in Ghost API
            update_data = {
                "posts": [{
                    "id": post_id,
                    "status": "published",
                    "updated_at": post_data.get("updated_at")
                }]
            }

            # Query parameters for email sending
            # newsletter: the slug of the newsletter to send to
            # email_segment: who should receive it (all, status:free, status:paid, etc.)
            query_params = {
                "newsletter": newsletter_slug,
                "email_segment": "all"  # Send to all newsletter subscribers
            }

            print(f"📤 Publishing post with email delivery...")
            print(f"   Newsletter: {newsletter_slug}")
            print(f"   Segment: all subscribers")

            # Publish the post with newsletter parameters
            # This triggers Ghost to queue the email for sending
            published_post = self._make_request(
                "PUT",
                f"posts/{post_id}/",
                data=update_data,
                params=query_params
            )

            post = published_post.get("posts", [{}])[0]

            self.last_published_url = post.get('url')

            print(f"✓ Post published and email queued for delivery")
            print(f"✓ Post URL: {self.last_published_url or 'N/A'}")
            print(f"📧 Email will be sent to all newsletter subscribers")

            return True

        except Exception as e:
            print(f"✗ Error sending email: {e}")
            print("📧 Make sure:")
            print("   - Ghost newsletter is configured in admin panel")
            print("   - Email service (Mailgun/SendGrid) is set up")
            print("   - Members are subscribed to the newsletter")
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
                'header-ids',
                'extra'  # Enables better list formatting
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
        
        # Remove ALL H1 tags (the redundant "Crypto Trading Signals" header from markdown, and any "Trading Signals - Leviathan News Edition" headers)
        # This is handled by the email template, so we don't need them in the content
        html_content = re.sub(
            r'<h1[^>]*>.*?</h1>\s*',
            '',
            html_content,
            flags=re.DOTALL
        )
        
        # Remove any duplicate "Leviathan News Daily Digest" text that might appear in the body
        html_content = re.sub(
            r'🦑\s*Leviathan News Daily Digest[^<]*',
            '',
            html_content,
            flags=re.IGNORECASE
        )
        
        # Clean up excessive whitespace/newlines at the start (after removing H1)
        html_content = re.sub(r'^(\s|<br\s*/?>)*', '', html_content, flags=re.MULTILINE)
        
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
        
        # Remove excessive newlines/whitespace before Market Snapshot
        # Match any whitespace or <br> tags before Market Snapshot H2
        html_content = re.sub(
            r'(\s|<br\s*/?>)+(?=<h2[^>]*>.*?Market Snapshot)',
            '\n',
            html_content,
            flags=re.IGNORECASE | re.DOTALL
        )
        
        # Add CSS margin-top to section headers for spacing
        # Instead of relying on <br> tags which may be lost in rendering,
        # add margin-top style directly to the headers
        section_headers = [
            'Top Stories',
            'Backtest Results',
            'Sell the News Strategy',
            'Performance vs Benchmarks',
            'Current Positions',
            'Trades Today',
        ]

        for header_name in section_headers:
            # Pattern: any whitespace/br before the header, then the header itself
            # Add margin-top for website display (email clients may override)
            pattern = f'(\\s|<br\\s*/?>)*(<h[2-4])([^>]*?)>([^<]*?{re.escape(header_name)}[^<]*?)(</h[2-4]>)'
            def add_margin(match):
                whitespace = match.group(1) or ''
                h_tag = match.group(2)
                attrs = match.group(3)
                content = match.group(4)
                close_tag = match.group(5)

                # Use smaller margin for email compatibility (email clients often ignore large margins)
                margin = '10px'

                # Check if there's already a style attribute
                if 'style=' in attrs:
                    # Add margin-top to existing style
                    attrs = re.sub(
                        r'style="([^"]*)"',
                        lambda m: f'style="margin-top: {margin}; {m.group(1)}"',
                        attrs
                    )
                else:
                    # Add new style attribute
                    attrs = f'{attrs} style="margin-top: {margin};"'

                # Remove excessive whitespace before the header
                return f'{h_tag}{attrs}>{content}{close_tag}'

            html_content = re.sub(
                pattern,
                add_margin,
                html_content,
                flags=re.IGNORECASE | re.DOTALL
            )
        
        # Remove excessive whitespace around horizontal rule (before disclaimer)
        # Email clients add padding, so we want minimal spacing here
        # Match any <br> tags or excessive whitespace before the HR
        html_content = re.sub(
            r'(<br\s*/?>|\s)+(<hr[^>]*>|---\s*)(\s*<br\s*/?>)*(?=\s*<p[^>]*>.*?Disclaimer)',
            r'\2',
            html_content,
            flags=re.IGNORECASE | re.DOTALL
        )
        
        # Clean up any excessive duplicate breaks (more than 2 consecutive <br> tags) - collapse to single <br>
        html_content = re.sub(r'(<br\s*/?>\s*){3,}', '<br>\n', html_content)
        
        # Convert SQUID Pass section to mobile-friendly layout
        html_content = self._convert_squid_pass_layout(html_content)
        
        # Convert table layout to improved story layout
        html_content = self._convert_table_to_story_layout(html_content)
        
        # Transform trading signals format
        html_content = self._transform_trading_signals(html_content)
        
        return html_content
    
    def _convert_squid_pass_layout(self, html_content: str) -> str:
        """Convert SQUID Pass winner table layout to mobile-friendly responsive layout.
        
        Args:
            html_content: HTML content with SQUID Pass table layout
            
        Returns:
            HTML content with improved SQUID Pass layout
        """
        import re
        
        # Pattern to match SQUID Pass winner section with table - more flexible to handle variations
        # Matches: div with orange border > table > tr (with orange background) > td with image > td with content
        # The headline can be in <strong> with or without a link, followed by " - " and source link
        # IMPORTANT: Only match the SQUID Pass row, not the entire table - use non-greedy matching and stop at </tr>
        # We'll handle the div/table wrapper removal separately
        squid_pass_pattern = r'<tr[^>]*style="[^"]*background-color:\s*#FFF5F2[^"]*"[^>]*>.*?<td[^>]*>.*?<img[^>]*src="([^"]*)"[^>]*>.*?</td>.*?<td[^>]*>(.*?)</td>.*?</tr>'
        
        def replace_squid_pass(match):
            img_url = match.group(1)
            content = match.group(2)
            
            # Extract h3 title
            h3_match = re.search(r'<h3[^>]*>([^<]*)</h3>', content)
            title = h3_match.group(1) if h3_match else "🏆 SQUID Pass Winner"
            
            # Extract headline - can be <strong>text</strong> or <strong><a>text</a></strong>
            headline_match = re.search(r'<strong[^>]*>(?:<a[^>]*href="([^"]*)"[^>]*>)?([^<]+)(?:</a>)?</strong>', content)
            if headline_match:
                canonical_url = headline_match.group(1) or "#"
                headline = headline_match.group(2).strip()
            else:
                canonical_url = "#"
                headline = ""
            
            # Extract source link (first <a> after the headline, after " - " and before any <br>)
            # Pattern: </strong> - <a>source</a> (before <br>)
            source_match = re.search(r'</strong>\s*-\s*<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>(?=[^<]*<br|$)', content)
            if source_match:
                source_url = source_match.group(1)
                source = source_match.group(2)
            else:
                # Fallback: find first link after headline that's not in tags or comments
                # Look for link after </strong> but before <br><span (tags) or <br>💬 (comment)
                fallback_match = re.search(r'</strong>[^<]*<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', content)
                if fallback_match:
                    source_url = fallback_match.group(1)
                    source = fallback_match.group(2)
                else:
                    source_url = "#"
                    source = "Source"
            
            # Extract tags from span
            tags_match = re.search(r'<span[^>]*>🏷️\s*(.*?)</span>', content, re.DOTALL)
            if tags_match:
                # Extract individual tag links
                tag_links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', tags_match.group(1))
                clickable_tags = []
                for url, text in tag_links:
                    clickable_tags.append(f'<a href="{url}" style="color: #021f53; text-decoration: none;">{text}</a>')
                tags = " • ".join(clickable_tags)
            else:
                tags = ""
            
            # Extract comment
            comment_match = re.search(r'💬\s*<i>([^<]*)</i>\s*—\s*@([^<\s]*)', content)
            if comment_match:
                comment = comment_match.group(1)
                username = comment_match.group(2)
            else:
                comment = ""
                username = ""
            
            # Build tags HTML if present
            tags_html = f'<div style="margin: 6px 0; font-size: 13px; color: #666;">🏷️ {tags}</div>' if tags else ""
            
            # Build comment HTML only if comment exists and is not empty
            comment_html = ""
            if comment and comment.strip():
                comment_html = f'''
                    <blockquote style="margin: 8px 0 0 0; padding: 8px 10px; background: #f8f9fa; border-left: 3px solid #FF6B35; font-style: italic; color: #555; font-size: 14px;">
                        {comment}
                        <br><small style="color: #666;"><a href="https://leviathannews.xyz/u/{username}/articles" style="color: #021f53; text-decoration: none;">@{username}</a></small>
                    </blockquote>
                '''
            
            return f'''
            <div class="squid-pass-section" style="border: 2px solid #FF6B35; border-radius: 8px; padding: 12px; margin-bottom: 24px; background-color: #FFF5F2; width: 100%; box-sizing: border-box;">
                <div style="text-align: center; margin-bottom: 8px;">
                    <img src="{img_url}" alt="SQUID Pass Winner" style="max-width: 100%; width: 100%; height: auto; border-radius: 6px; border: 2px solid #FF6B35; display: block;">
                </div>
                <div style="padding: 0;">
                    <h3 style="margin: 0 0 8px 0; color: #FF6B35; font-size: 20px;">🏆 SQUID Pass Winner</h3>
                    <p style="margin: 0 0 8px 0; font-size: 16px; line-height: 1.4;">
                        <strong><a href="{canonical_url}" style="color: #021f53; text-decoration: none;">{headline}</a></strong>
                    </p>
                    <p style="margin: 0 0 8px 0; color: #666; font-size: 14px;">
                        Source: <a href="{source_url}" style="color: #021f53; text-decoration: none;">{source}</a>
                    </p>
                    {tags_html}
                    {comment_html}
                </div>
            </div>
            '''
        
        html_content = re.sub(squid_pass_pattern, replace_squid_pass, html_content, flags=re.DOTALL)
        
        return html_content
    
    def _convert_table_to_story_layout(self, html_content: str) -> str:
        """Convert table-based story layout to improved full-width layout.
        
        Args:
            html_content: HTML content with table layout
            
        Returns:
            HTML content with improved story layout
        """
        import re
        
        # First, remove the orange border div wrapper that was around the entire table
        # This should only wrap SQUID Pass, not all stories
        html_content = re.sub(
            r'<div[^>]*style="[^"]*border:\s*2px\s+solid\s+#FF6B35[^"]*"[^>]*>\s*<table',
            '<table',
            html_content,
            flags=re.DOTALL
        )
        html_content = re.sub(
            r'</table>\s*</div>',
            '</table>',
            html_content,
            flags=re.DOTALL
        )
        
        # More flexible pattern to match story rows - handles the exact structure we see
        # EXCLUDE SQUID Pass rows (they have h3 with "SQUID Pass Winner" or background-color: #FFF5F2)
        story_pattern = r'<tr(?!\s+style="[^"]*background-color:\s*#FFF5F2[^"]*")(?![^>]*>.*?<h3[^>]*>.*?SQUID Pass Winner)[^>]*>\s*<td[^>]*>\s*<img[^>]*src="([^"]*)"[^>]*>\s*</td>\s*<td[^>]*>\s*<strong><a[^>]*href="([^"]*)"[^>]*>([^<]*)</a></strong>[^<]*<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>\s*<br><span[^>]*>🏷️\s*([^<]*)</span>\s*<br>💬\s*<i>([^<]*)</i>\s*—\s*@([^<\s]*)'
        
        def replace_story(match):
            img_url = match.group(1)
            story_url = match.group(2)
            story_title = match.group(3)
            source_url = match.group(4)
            source_text = match.group(5)
            tags = match.group(6)
            comment = match.group(7)
            username = match.group(8)
            
            # Only show comment blockquote if comment exists and is not empty
            comment_html = ""
            if comment and comment.strip():
                comment_html = f'''
                    <blockquote style="margin: 8px 0 0 0; padding: 8px 10px; background: #f8f9fa; border-left: 3px solid #021f53; font-style: italic; color: #555; font-size: 14px;">
                        {comment}
                        <br><small style="color: #666;"><a href="https://leviathannews.xyz/u/{username}/articles" style="color: #021f53; text-decoration: none;">@{username}</a></small>
                    </blockquote>
                '''
            
            # Create improved story layout with minimal padding for mobile
            return f'''
            <div class="story-section" style="margin-bottom: 16px; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; width: 100%; box-sizing: border-box;">
                <a href="{story_url}" style="display: block; text-decoration: none;">
                    <img src="{img_url}" alt="Story Image" style="width: 100%; height: 200px; object-fit: cover; display: block;">
                </a>
                <div style="padding: 8px;">
                    <h3 style="margin: 0 0 6px 0; font-size: 18px; line-height: 1.4; color: #333;">
                        {story_title}
                    </h3>
                    <p style="margin: 0 0 6px 0; color: #666; font-size: 14px;">
                        Source: <a href="{source_url}" style="color: #021f53; text-decoration: none;">{source_text}</a>
                    </p>
                    <div style="margin: 6px 0; font-size: 13px; color: #666;">
                        🏷️ {tags}
                    </div>
                    {comment_html}
                </div>
            </div>
            '''
        
        # Try the complex pattern first
        html_content = re.sub(story_pattern, replace_story, html_content, flags=re.DOTALL)
        
        # If that didn't work, try a simpler approach - just replace the table structure
        # But EXCLUDE SQUID Pass rows
        if '<tr>' in html_content and '<td' in html_content:
            # Fallback: simpler pattern that just extracts the key elements
            # Skip rows that contain SQUID Pass Winner or have the orange background
            simple_pattern = r'<tr(?!\s+style="[^"]*background-color:\s*#FFF5F2[^"]*")(?![^>]*>.*?<h3[^>]*>.*?SQUID Pass Winner)[^>]*>\s*<td[^>]*>\s*<img[^>]*src="([^"]*)"[^>]*>\s*</td>\s*<td[^>]*>\s*(.*?)\s*</td>\s*</tr>'
            
            def simple_replace(match):
                img_url = match.group(1)
                content = match.group(2)
                
                # Skip if this is a SQUID Pass row
                if 'SQUID Pass Winner' in content or '<h3' in content:
                    return match.group(0)  # Return unchanged
                
                # Extract story title - try numbered format first (e.g., "1. Story title")
                # Regular stories have: <strong>1. Story title</strong> or <strong><a>1. Story title</a></strong>
                title_match = re.search(r'<strong>(?:<a[^>]*href="([^"]*)"[^>]*>)?(\d+\.\s*[^<]+)(?:</a>)?</strong>', content)
                if title_match:
                    story_url = title_match.group(1) or "#"
                    story_title = title_match.group(2).strip()
                else:
                    # Try without number prefix
                    title_match = re.search(r'<strong><a[^>]*href="([^"]*)"[^>]*>([^<]*)</a></strong>', content)
                    if title_match:
                        story_url = title_match.group(1)
                        story_title = title_match.group(2)
                    else:
                        # Try just <strong> without link
                        title_match = re.search(r'<strong>([^<]+)</strong>', content)
                        if title_match:
                            story_url = "#"
                            story_title = title_match.group(1).strip()
                        else:
                            story_url = "#"
                            story_title = "Story"
                
                # Extract source (second <a> tag, after the title)
                all_links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', content)
                if len(all_links) >= 2:
                    # Second link is the source
                    source_url = all_links[1][0]
                    source_text = all_links[1][1]
                elif len(all_links) == 1:
                    # Only one link, use it as source
                    source_url = all_links[0][0]
                    source_text = all_links[0][1]
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
                
                # Only show comment blockquote if comment exists and is not empty
                comment_html = ""
                if comment and comment.strip():
                    comment_html = f'''
                        <blockquote style="margin: 15px 0 0 0; padding: 10px 15px; background: #f8f9fa; border-left: 3px solid #021f53; font-style: italic; color: #555; font-size: 14px;">
                            {comment}
                            <br><small style="color: #666;"><a href="https://leviathannews.xyz/u/{username}/articles" style="color: #021f53; text-decoration: none;">@{username}</a></small>
                        </blockquote>
                    '''
                
                return f'''
                <div class="story-section" style="margin-bottom: 16px; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; width: 100%; box-sizing: border-box;">
                    <a href="{story_url}" style="display: block; text-decoration: none;">
                        <img src="{img_url}" alt="Story Image" style="width: 100%; height: 200px; object-fit: cover; display: block;">
                    </a>
                    <div style="padding: 8px;">
                        <h3 style="margin: 0 0 6px 0; font-size: 18px; line-height: 1.4; color: #333;">
                            {story_title}
                        </h3>
                        <p style="margin: 0 0 6px 0; color: #666; font-size: 14px;">
                            Source: <a href="{source_url}" style="color: #021f53; text-decoration: none;">{source_text}</a>
                        </p>
                        <div style="margin: 6px 0; font-size: 13px; color: #666;">
                            🏷️ {tags}
                        </div>
                        {comment_html}
                    </div>
                </div>
                '''
            
            html_content = re.sub(simple_pattern, simple_replace, html_content, flags=re.DOTALL)
        
        # Remove the table wrapper if it's empty
        html_content = re.sub(r'<table[^>]*>\s*</table>', '', html_content)
        
        return html_content
    
    def _get_token_id_map(self) -> Dict[str, Dict[str, Any]]:
        """Get a mapping of token symbols to Leviathan canonical tags.
        
        Returns:
            Dictionary mapping symbol -> {canonical_tag, name}
        """
        cache_file = Path(".data/leviathan_token_id_map.json")
        
        # Try to load from cache first
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    import json
                    return json.load(f)
            except Exception:
                pass
        
        # If cache doesn't exist, return empty dict (will be populated by digest.py)
        return {}
    
    def _transform_trading_signals(self, html_content: str) -> str:
        """Transform trading signals format to new style with emoji and hyperlinked symbols.
        
        Transforms from: <p><strong>$BTC Bitcoin: STRONG BUY</strong> - reason</p>
        To: <p>🟢 Bitcoin (<a href="...">$BTC</a>): STRONG BUY - reason</p>
        
        Args:
            html_content: HTML content with trading signals
            
        Returns:
            HTML content with transformed trading signals
        """
        import json
        
        # Get token ID mapping
        token_id_map = self._get_token_id_map()
        
        # Signal type to emoji mapping
        # Using red/green circles for sell/buy signals
        signal_emoji_map = {
            'STRONG BUY': '🟢',
            'BUY': '🟢',
            'WEAK BUY': '🟡',
            'WEAK SELL': '🟠',
            'SELL': '🔴',
            'STRONG SELL': '🔴'
        }
        
        # Pattern to match: <p><strong>$SYMBOL Token Name: SIGNAL</strong> - reason</p>
        # Also handles cases where there might be markdown links like ([more info](URL))
        signal_pattern = re.compile(
            r'<p><strong>\$([A-Za-z0-9]+)\s+([^:]+?):\s+([A-Z\s]+)</strong>\s*-\s*(.*?)(?:\(\[more info\]\([^)]+\)\))?</p>',
            re.MULTILINE | re.DOTALL
        )
        
        def transform_signal(match):
            symbol = match.group(1).upper()
            token_name = match.group(2).strip()
            signal_type = match.group(3).strip()
            reason = match.group(4).strip()
            
            # Get emoji for signal type
            emoji = signal_emoji_map.get(signal_type, '⚪')
            
            # Get token canonical_tag for link
            token_info = token_id_map.get(symbol, {})
            canonical_tag = token_info.get('canonical_tag')
            token_name_from_map = token_info.get('name', token_name)
            
            # Use token name from map if available, otherwise use parsed name
            display_name = token_name_from_map if token_name_from_map else token_name
            
            # Create link if we have canonical_tag
            if canonical_tag:
                link = f"https://leviathannews.xyz/t/{canonical_tag}/{symbol}?utm_medium=digest&utm_source=digest&utm_campaign=trading_signals"
                symbol_link = f'<a href="{link}" style="color: #021f53; text-decoration: none;">${symbol}</a>'
            else:
                symbol_link = f'${symbol}'
            
            # Format as: EMOJI Token Name (SYMBOL hyperlinked): SIGNAL - reason
            # Note: Signal type should be bold per user's example
            return f'<p>{emoji} {display_name} ({symbol_link}): <strong>{signal_type}</strong> - {reason}</p>'
        
        # Find Trading Signals section and transform signals within it
        trading_signals_section = re.search(
            r'(<h2[^>]*>.*?Trading Signals.*?</h2>.*?)(.*?)(?=<h[12]|$)',
            html_content,
            re.DOTALL | re.IGNORECASE
        )
        
        if trading_signals_section:
            section_header = trading_signals_section.group(1)
            section_content = trading_signals_section.group(2)
            
            # Transform all signals in the section
            transformed_content = signal_pattern.sub(transform_signal, section_content)
            
            # Replace the section in the original HTML
            html_content = html_content.replace(
                trading_signals_section.group(0),
                section_header + transformed_content
            )
        else:
            # If we can't find the section, try transforming the whole content
            html_content = signal_pattern.sub(transform_signal, html_content)
        
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
        admin_emails = os.getenv("ADMIN_EMAILS", "squid@leviathannews.xyz").split(",")
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
    
    def send_digest_email(self, digest_path: str, recipients: Optional[List[str]] = None, existing_post_id: Optional[str] = None) -> bool:
        """Send digest email to public recipients via Ghost.

        Args:
            digest_path: Path to the digest markdown file
            recipients: List of recipient emails. If None, gets all subscribers from Ghost.
            existing_post_id: If provided, update and publish this draft instead of creating a new post.
                              Prevents slug collisions when a draft was already created.

        Returns:
            True if email sent successfully, False otherwise
        """
        if recipients is None:
            # Get all subscribers from Ghost (those with "subscriber" label)
            print("Fetching all subscribers from Ghost...")
            subscriber_members = self.get_members("label:subscriber")
            
            if subscriber_members:
                recipients = [member.get("email") for member in subscriber_members if member.get("email")]
                print(f"Found {len(recipients)} subscribers in Ghost")
            else:
                # Fallback to PUBLIC_EMAILS env var if no subscribers found in Ghost
                print("No subscribers found in Ghost, falling back to PUBLIC_EMAILS env var")
                public_emails = os.getenv("PUBLIC_EMAILS", "squid@leviathannews.xyz,kraken@leviathannews.xyz").split(",")
                recipients = [email.strip() for email in public_emails if email.strip()]
                # Ensure these members exist with subscriber label and are subscribed to newsletter
                for email in recipients:
                    member = self.ensure_member_exists(email, labels=["subscriber"])
                    # Try to ensure member is subscribed to default newsletter
                    try:
                        newsletters = self._make_request("GET", "newsletters/")
                        if newsletters.get("newsletters"):
                            newsletter_id = newsletters["newsletters"][0].get("id")
                            # Subscribe member to newsletter (if not already subscribed)
                            # Note: Ghost API doesn't have direct subscribe endpoint, 
                            # members need to subscribe via signup form or admin panel
                            print(f"Note: Member {email} should be subscribed to newsletter {newsletter_id}")
                    except Exception as e:
                        print(f"Warning: Could not check newsletter subscription for {email}: {e}")
        
        if not recipients:
            print("No recipients configured")
            return False
        
        print(f"Sending digest email to {len(recipients)} recipient(s)")
        
        # Read digest content
        digest_file = Path(digest_path)
        if not digest_file.exists():
            print(f"Digest file not found: {digest_path}")
            return False
        
        with open(digest_file, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # Extract date from filename
        parsed_date = dt.now()
        try:
            date_part = digest_file.stem.split("_")[-1]
            parsed_date = dt.strptime(date_part, "%Y-%m-%d")
        except (ValueError, IndexError):
            pass
        date_str = parsed_date.strftime("%B %d, %Y")

        # Convert to HTML
        html_digest_content = self.format_digest_html(markdown_content)

        # Generate full email HTML
        html_content = public_digest_template(html_digest_content, date_str)

        # Generate title using shared helper
        from squid_digest.config import get_digest_title
        title = get_digest_title(parsed_date)

        if existing_post_id:
            # Update the existing draft with final content before publishing
            try:
                existing = self._make_request("GET", f"posts/{existing_post_id}/")
                updated_at = existing.get("posts", [{}])[0].get("updated_at")
                mobiledoc = self._html_to_mobiledoc(html_content)
                update_data = {
                    "posts": [{
                        "id": existing_post_id,
                        "title": title,
                        "mobiledoc": mobiledoc,
                        "updated_at": updated_at,
                    }]
                }
                self._make_request("PUT", f"posts/{existing_post_id}/", update_data)
                post_id = existing_post_id
                print(f"✓ Updated existing draft: {post_id}")
            except Exception as e:
                print(f"⚠ Could not update existing draft ({e}), creating new post")
                post = self.create_post(title, html_content, status="draft", send_email=False)
                post_id = post["id"]
                print(f"✓ New draft post created: {post_id}")
        else:
            post = self.create_post(title, html_content, status="draft", send_email=False)
            post_id = post["id"]
            print(f"✓ Draft post created: {post_id}")

        # Reset before publish so stale URLs don't carry over
        self.last_published_url = None

        # Publish with newsletter parameters to trigger email sending
        return self.send_email_to_members(post_id, "label:subscriber")
    
    def send_test_email_to_admins(self, digest_path: str) -> bool:
        """Send test email with actual digest content to admins for review.
        
        This sends the full digest content to admins so they can preview
        what subscribers will receive. This is sent on first run.
        
        Args:
            digest_path: Path to the digest markdown file
            
        Returns:
            True if email sent successfully, False otherwise
        """
        admin_emails = os.getenv("ADMIN_EMAILS", "squid@leviathannews.xyz").split(",")
        admin_emails = [email.strip() for email in admin_emails if email.strip()]
        
        if not admin_emails:
            print("No admin emails configured")
            return False
        
        print(f"Attempting to send test email to admins: {', '.join(admin_emails)}")
        
        # Ensure admin members exist with admin label
        for email in admin_emails:
            try:
                self.ensure_member_exists(email, labels=["admin"])
            except Exception as e:
                print(f"Warning: Could not manage member {email}: {e}")
        
        # Read digest content
        digest_file = Path(digest_path)
        if not digest_file.exists():
            print(f"Digest file not found: {digest_path}")
            return False
        
        with open(digest_file, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # Extract date from filename or content
        date_str = dt.now().strftime("%B %d, %Y")
        if "signals_" in digest_file.name or "digest_" in digest_file.name:
            try:
                date_part = digest_file.stem.split("_")[-1]  # Get date part
                parsed_date = dt.strptime(date_part, "%Y-%m-%d")
                date_str = parsed_date.strftime("%B %d, %Y")
            except:
                pass  # Use current date if parsing fails
        
        # Convert to HTML
        html_digest_content = self.format_digest_html(markdown_content)
        
        # Generate full email HTML with test banner
        html_content = self._test_digest_template(html_digest_content, date_str)
        
        # Generate title with test prefix
        title = f"🧪 TEST: Leviathan News Daily Digest - {date_str}"
        
        # Create post in Ghost
        post = self.create_post(title, html_content, status="draft")
        
        # Send email to admin members
        return self.send_email_to_members(post["id"], "label:admin")
    
    def _test_digest_template(self, content: str, date: str) -> str:
        """Generate HTML template for test digest email with admin banner."""
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; width: 100%; max-width: 100%; margin: 0; padding: 0;">
            <table role="presentation" style="width: 100%; border-collapse: collapse; margin: 0; padding: 0;">
                <tr>
                    <td style="padding: 0;">
                        <div style="max-width: 650px; margin: 0 auto; padding: 20px;">
                            <div style="background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
                                <h2 style="margin: 0; font-size: 20px;">🧪 TEST EMAIL - ADMIN PREVIEW</h2>
                                <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 14px;">This is a preview of what subscribers will receive in 1 hour</p>
                            </div>
                            
                            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 20px;">
                                <h1 style="margin: 0; font-size: 28px;">📊 Crypto Trading Signals</h1>
                                <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 18px;">{date}</p>
                                <p style="margin: 10px 0 0 0; opacity: 0.8;">Squid Digest - AI-powered insights for crypto natives</p>
                            </div>
                            
                            <div style="background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                                <div style="background: #f8f9fa; padding: 20px; border-radius: 6px;">
                                    {content}
                                </div>
                            </div>
                            
                            <div style="text-align: center; color: #666; font-size: 14px;">
                                <p>Generated by Squid Digest - AI-powered trading signals for crypto natives</p>
                                <p>Powered by Leviathan News & Perplexity AI</p>
                            </div>
                        </div>
                    </td>
                </tr>
            </table>
        </div>
        """
    
    def send_edit_notification(self, digest_path: str, github_url: str, changes_summary: str = "") -> bool:
        """Send edit notification email to admins via Ghost.
        
        Args:
            digest_path: Path to the digest file
            github_url: GitHub URL to the digest file
            changes_summary: Summary of changes made
            
        Returns:
            True if email sent successfully, False otherwise
        """
        admin_emails = os.getenv("ADMIN_EMAILS", "squid@leviathannews.xyz").split(",")
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
