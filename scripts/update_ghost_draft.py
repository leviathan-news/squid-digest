#!/usr/bin/env python3
"""
Update Ghost draft with corrected content from signals markdown file.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from squid_digest.email import GhostEmailClient

def update_ghost_draft(signals_file: str, post_id: str = None):
    """Update or create Ghost draft from signals markdown file.
    
    Args:
        signals_file: Path to signals markdown file
        post_id: Optional Ghost post ID to update (if None, creates new draft)
    """
    signals_path = Path(signals_file)
    if not signals_path.exists():
        print(f"Error: Signals file not found: {signals_file}")
        return False
    
    # Read the markdown content
    content = signals_path.read_text()
    
    # Initialize Ghost client
    try:
        client = GhostEmailClient()
    except Exception as e:
        print(f"Error initializing Ghost client: {e}")
        print("Make sure GHOST_URL and GHOST_ADMIN_API_KEY are set")
        return False
    
    # Convert to HTML
    html_content = client.format_digest_html(content)
    
    # Extract date from filename and use shared title
    from squid_digest.config import get_digest_title
    date_str = signals_path.stem.split("_")[-1]  # e.g., "2025-12-06"
    from datetime import datetime
    title = get_digest_title(datetime.strptime(date_str, "%Y-%m-%d"))
    
    # Update existing post or create new one
    if post_id:
        # First, fetch the existing post to get updated_at timestamp
        try:
            existing_post = client._make_request("GET", f"posts/{post_id}/")
            existing_post_data = existing_post.get("posts", [{}])[0]
            updated_at = existing_post_data.get("updated_at")
            
            if not updated_at:
                print(f"Warning: Could not get updated_at from existing post. Creating new draft instead.")
                post_id = None
            else:
                # Update existing post with updated_at
                mobiledoc = client._html_to_mobiledoc(html_content)
                post_data = {
                    "posts": [{
                        "id": post_id,
                        "title": title,
                        "mobiledoc": mobiledoc,
                        "status": "draft",
                        "updated_at": updated_at
                    }]
                }
                
                response = client._make_request("PUT", f"posts/{post_id}/", post_data)
                updated_post = response.get("posts", [{}])[0]
                print(f"✓ Updated Ghost draft: {updated_post.get('id', post_id)}")
                print(f"  URL: {client.ghost_url}/#/editor/post/{updated_post.get('id', post_id)}")
                return True
        except Exception as e:
            print(f"Error fetching/updating post: {e}")
            print("Creating new draft instead...")
            post_id = None
    else:
        # Create new draft
        try:
            post = client.create_post(title, html_content, status="draft")
            print(f"✓ Created new Ghost draft: {post.get('id', 'unknown')}")
            print(f"  URL: {client.ghost_url}/#/editor/post/{post.get('id', 'unknown')}")
            return True
        except Exception as e:
            print(f"Error creating post: {e}")
            return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Update Ghost draft with signals content")
    parser.add_argument("signals_file", help="Path to signals markdown file")
    parser.add_argument("--post-id", help="Ghost post ID to update (if not provided, creates new draft)")
    
    args = parser.parse_args()
    
    success = update_ghost_draft(args.signals_file, args.post_id)
    sys.exit(0 if success else 1)

