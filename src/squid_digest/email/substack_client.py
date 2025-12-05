"""Substack client for Squid Digest draft generation."""

import os
import re
from datetime import datetime as dt
from pathlib import Path
from typing import Optional
import markdown2


class SubstackClient:
    """Client for generating Substack-ready draft files.
    
    Since Substack doesn't have an official API, this client generates
    HTML files that can be copy-pasted into Substack's editor.
    """
    
    def __init__(self):
        """Initialize Substack client."""
        pass
    
    def format_digest_for_substack(self, markdown_content: str) -> str:
        """Convert markdown digest content to Substack-compatible HTML.
        
        Substack's editor accepts HTML paste but strips complex CSS and formatting.
        This method creates simpler HTML that works well in Substack.
        
        Args:
            markdown_content: Raw markdown content
            
        Returns:
            HTML formatted content optimized for Substack editor
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
        
        # Post-process HTML for Substack compatibility
        html_content = self._format_for_substack(html_content)
        
        return html_content
    
    def _format_for_substack(self, html_content: str) -> str:
        """Format HTML content specifically for Substack editor.
        
        Substack's editor:
        - Accepts HTML paste but simplifies it
        - Strips complex CSS and inline styles
        - Preserves basic structure: headers, paragraphs, links, images
        - Works better with simpler HTML
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            Substack-compatible HTML content
        """
        import re
        
        # Remove H1 tags (handled by Substack title field)
        html_content = re.sub(
            r'<h1[^>]*>.*?</h1>\s*',
            '',
            html_content,
            flags=re.DOTALL
        )
        
        # Remove duplicate "Leviathan News Daily Digest" text
        html_content = re.sub(
            r'🦑\s*Leviathan News Daily Digest[^<]*',
            '',
            html_content,
            flags=re.IGNORECASE
        )
        
        # Clean up excessive whitespace
        html_content = re.sub(r'^(\s|<br\s*/?>)*', '', html_content, flags=re.MULTILINE)
        
        # Simplify link styling - Substack will apply its own styles
        # Keep links but remove complex inline styles
        html_content = re.sub(
            r'<a([^>]*)style="[^"]*"([^>]*)>',
            r'<a\1\2>',
            html_content
        )
        
        # Simplify complex div structures - Substack prefers simpler HTML
        # Convert styled divs to simpler structures where possible
        html_content = self._simplify_divs(html_content)
        
        # Convert SQUID Pass section to simpler format
        html_content = self._convert_squid_pass_for_substack(html_content)
        
        # Convert table layout to simpler story format
        html_content = self._convert_stories_for_substack(html_content)
        
        # Transform trading signals format
        html_content = self._transform_trading_signals(html_content)
        
        # Clean up excessive breaks
        html_content = re.sub(r'(<br\s*/?>\s*){3,}', '<br><br>\n', html_content)
        
        return html_content
    
    def _simplify_divs(self, html_content: str) -> str:
        """Simplify complex div structures for Substack compatibility.
        
        Args:
            html_content: HTML content with complex divs
            
        Returns:
            HTML with simplified div structures
        """
        import re
        
        # Remove complex inline styles from divs that Substack will strip anyway
        # Keep basic structure but remove styling
        html_content = re.sub(
            r'<div([^>]*)style="[^"]*"([^>]*)>',
            r'<div\1\2>',
            html_content
        )
        
        return html_content
    
    def _convert_squid_pass_for_substack(self, html_content: str) -> str:
        """Convert SQUID Pass winner section for Substack.
        
        Args:
            html_content: HTML content with SQUID Pass section
            
        Returns:
            HTML with Substack-compatible SQUID Pass section
        """
        import re
        
        # Pattern to match SQUID Pass winner section
        squid_pass_pattern = r'<tr[^>]*style="[^"]*background-color:\s*#FFF5F2[^"]*"[^>]*>.*?<td[^>]*>.*?<img[^>]*src="([^"]*)"[^>]*>.*?</td>.*?<td[^>]*>(.*?)</td>.*?</tr>'
        
        def replace_squid_pass(match):
            img_url = match.group(1)
            content = match.group(2)
            
            # Extract headline
            headline_match = re.search(r'<strong[^>]*>(?:<a[^>]*href="([^"]*)"[^>]*>)?([^<]+)(?:</a>)?</strong>', content)
            if headline_match:
                canonical_url = headline_match.group(1) or "#"
                headline = headline_match.group(2).strip()
            else:
                canonical_url = "#"
                headline = ""
            
            # Extract source
            source_match = re.search(r'</strong>\s*-\s*<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', content)
            if source_match:
                source_url = source_match.group(1)
                source = source_match.group(2)
            else:
                source_url = "#"
                source = "Source"
            
            # Extract tags
            tags_match = re.search(r'<span[^>]*>🏷️\s*(.*?)</span>', content, re.DOTALL)
            if tags_match:
                tag_links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', tags_match.group(1))
                clickable_tags = []
                for url, text in tag_links:
                    clickable_tags.append(f'<a href="{url}">{text}</a>')
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
            
            # Build simpler HTML for Substack
            tags_html = f'<p>🏷️ {tags}</p>' if tags else ""
            comment_html = f'<blockquote>{comment} — <a href="https://leviathannews.xyz/u/{username}/articles">@{username}</a></blockquote>' if comment else ""
            
            return f'''
            <h3>🏆 SQUID Pass Winner</h3>
            <p><img src="{img_url}" alt="SQUID Pass Winner" /></p>
            <p><strong><a href="{canonical_url}">{headline}</a></strong></p>
            <p>Source: <a href="{source_url}">{source}</a></p>
            {tags_html}
            {comment_html}
            '''
        
        html_content = re.sub(squid_pass_pattern, replace_squid_pass, html_content, flags=re.DOTALL)
        return html_content
    
    def _convert_stories_for_substack(self, html_content: str) -> str:
        """Convert story layout to simpler format for Substack.
        
        The new format is already vertical (div-based), so this mainly
        cleans up styles and ensures Substack compatibility.
        
        Args:
            html_content: HTML content with story divs
            
        Returns:
            HTML with simplified story format
        """
        import re
        
        # Pattern to match story divs (new vertical format)
        # Matches divs with padding and border-bottom that contain images and story content
        story_pattern = r'<div[^>]*style="[^"]*padding:\s*16px[^"]*border-bottom[^"]*"[^>]*>\s*(?:<img[^>]*src="([^"]*)"[^>]*>)?\s*(.*?)\s*</div>'
        
        def replace_story(match):
            img_url = match.group(1) if match.group(1) else ""
            content = match.group(2)
            
            # Skip SQUID Pass rows (they have background-color: #FFF5F2)
            if 'SQUID Pass Winner' in content:
                return match.group(0)
            
            # Extract story number and headline
            # Format: "1. Headline text - <a href="..."><strong>Source</strong></a>"
            headline_match = re.search(r'(\d+)\.\s*([^<]+)\s*-\s*<a[^>]*href="([^"]*)"[^>]*><strong>([^<]+)</strong></a>', content)
            if headline_match:
                story_num = headline_match.group(1)
                story_title = headline_match.group(2).strip()
                story_url = headline_match.group(3)
                source_text = headline_match.group(4)
            else:
                # Fallback: try to extract from paragraph
                p_match = re.search(r'<p[^>]*>(\d+)\.\s*([^<]+)\s*-\s*<a[^>]*href="([^"]*)"[^>]*><strong>([^<]+)</strong></a>', content)
                if p_match:
                    story_num = p_match.group(1)
                    story_title = p_match.group(2).strip()
                    story_url = p_match.group(3)
                    source_text = p_match.group(4)
                else:
                    story_num = ""
                    story_title = "Story"
                    story_url = "#"
                    source_text = "Source"
            
            # Extract tags from paragraph
            tags_match = re.search(r'<p[^>]*>🏷️\s*(.*?)</p>', content, re.DOTALL)
            if tags_match:
                tag_links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', tags_match.group(1))
                clickable_tags = []
                for url, text in tag_links:
                    clickable_tags.append(f'<a href="{url}">{text}</a>')
                tags = " • ".join(clickable_tags)
            else:
                tags = ""
            
            # Extract comment
            comment_match = re.search(r'💬\s*<i>([^<]*)</i>\s*—\s*<a[^>]*href="[^"]*">@([^<\s]*)</a>', content)
            if comment_match:
                comment = comment_match.group(1)
                username = comment_match.group(2)
            else:
                comment = ""
                username = ""
            
            # Build simpler HTML for Substack (format is already vertical, just clean up)
            img_html = f'<p><img src="{img_url}" alt="Story Image" /></p>' if img_url else ""
            tags_html = f'<p>🏷️ {tags}</p>' if tags else ""
            comment_html = f'<blockquote>{comment} — <a href="https://leviathannews.xyz/u/{username}/articles">@{username}</a></blockquote>' if comment else ""
            
            return f'''
            {img_html}
            <h3>{story_num}. <a href="{story_url}">{story_title}</a></h3>
            <p>Source: <a href="{story_url}">{source_text}</a></p>
            {tags_html}
            {comment_html}
            '''
        
        html_content = re.sub(story_pattern, replace_story, html_content, flags=re.DOTALL)
        
        # Remove empty tables (if any remain from old format)
        html_content = re.sub(r'<table[^>]*>\s*</table>', '', html_content)
        
        return html_content
    
    def _get_token_id_map(self) -> dict:
        """Get a mapping of token symbols to Leviathan canonical tags.
        
        Returns:
            Dictionary mapping symbol -> {canonical_tag, name}
        """
        cache_file = Path(".data/leviathan_token_id_map.json")
        
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    import json
                    return json.load(f)
            except Exception:
                pass
        
        return {}
    
    def _transform_trading_signals(self, html_content: str) -> str:
        """Transform trading signals format for Substack.
        
        Args:
            html_content: HTML content with trading signals
            
        Returns:
            HTML with transformed trading signals
        """
        import re
        
        token_id_map = self._get_token_id_map()
        
        signal_emoji_map = {
            'STRONG BUY': '🟢',
            'BUY': '🟢',
            'WEAK BUY': '🟡',
            'WEAK SELL': '🟠',
            'SELL': '🔴',
            'STRONG SELL': '🔴'
        }
        
        signal_pattern = re.compile(
            r'<p><strong>\$([A-Za-z0-9]+)\s+([^:]+?):\s+([A-Z\s]+)</strong>\s*-\s*(.*?)(?:\(\[more info\]\([^)]+\)\))?</p>',
            re.MULTILINE | re.DOTALL
        )
        
        def transform_signal(match):
            symbol = match.group(1).upper()
            token_name = match.group(2).strip()
            signal_type = match.group(3).strip()
            reason = match.group(4).strip()
            
            emoji = signal_emoji_map.get(signal_type, '⚪')
            
            token_info = token_id_map.get(symbol, {})
            canonical_tag = token_info.get('canonical_tag')
            token_name_from_map = token_info.get('name', token_name)
            
            display_name = token_name_from_map if token_name_from_map else token_name
            
            if canonical_tag:
                link = f"https://leviathannews.xyz/t/{canonical_tag}/{symbol}?utm_medium=digest&utm_source=digest&utm_campaign=trading_signals"
                symbol_link = f'<a href="{link}">${symbol}</a>'
            else:
                symbol_link = f'${symbol}'
            
            return f'<p>{emoji} {display_name} ({symbol_link}): <strong>{signal_type}</strong> - {reason}</p>'
        
        trading_signals_section = re.search(
            r'(<h2[^>]*>.*?Trading Signals.*?</h2>.*?)(.*?)(?=<h[12]|$)',
            html_content,
            re.DOTALL | re.IGNORECASE
        )
        
        if trading_signals_section:
            section_header = trading_signals_section.group(1)
            section_content = trading_signals_section.group(2)
            transformed_content = signal_pattern.sub(transform_signal, section_content)
            html_content = html_content.replace(
                trading_signals_section.group(0),
                section_header + transformed_content
            )
        else:
            html_content = signal_pattern.sub(transform_signal, html_content)
        
        return html_content
    
    def create_draft_file(self, digest_path: str, output_path: Optional[str] = None) -> Path:
        """Create a Substack-ready draft HTML file.
        
        Args:
            digest_path: Path to the markdown digest file
            output_path: Optional output path. If None, creates file next to digest_path
            
        Returns:
            Path to the created draft file
        """
        digest_file = Path(digest_path)
        if not digest_file.exists():
            raise FileNotFoundError(f"Digest file not found: {digest_path}")
        
        # Read markdown content
        with open(digest_file, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # Extract date from filename or use current date
        date_str = dt.now().strftime("%B %d, %Y")
        if "signals_" in digest_file.name or "digest_" in digest_file.name:
            try:
                date_part = digest_file.stem.split("_")[-1]
                parsed_date = dt.strptime(date_part, "%Y-%m-%d")
                date_str = parsed_date.strftime("%B %d, %Y")
            except:
                pass
        
        # Format content for Substack
        html_content = self.format_digest_for_substack(markdown_content)
        
        # Generate title
        title = f"🦑 Leviathan News Daily Digest - {date_str}"
        
        # Create full HTML document
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
</head>
<body>
    <h1>{title}</h1>
    {html_content}
</body>
</html>"""
        
        # Determine output path
        if output_path:
            output_file = Path(output_path)
        else:
            # Create next to digest file with substack_ prefix
            output_file = digest_file.parent / f"substack_draft_{digest_file.stem}.html"
        
        # Write file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_html)
        
        print(f"✓ Created Substack draft file: {output_file}")
        return output_file






