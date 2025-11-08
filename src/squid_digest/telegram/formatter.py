"""Formatter for converting digest content to Telegram-compatible HTML."""

import re
import html
from typing import List
import markdown2


def format_for_telegram(markdown_content: str, max_length: int = 4096) -> List[str]:
    """Convert markdown digest content to Telegram-compatible HTML.
    
    Args:
        markdown_content: Raw markdown content from signals file
        max_length: Maximum message length (Telegram limit is 4096)
        
    Returns:
        List of formatted HTML messages (split if content exceeds max_length)
    """
    # Convert markdown to HTML first
    html_content = markdown2.markdown(
        markdown_content,
        extras=[
            'fenced-code-blocks',
            'tables',
            'header-ids'
        ]
    )
    
    # Convert tables to Telegram-friendly list format
    telegram_html = _convert_tables_to_lists(html_content)
    
    # Clean up HTML to use only Telegram-supported tags
    telegram_html = _clean_telegram_html(telegram_html)
    
    # Split into multiple messages if needed
    messages = _split_messages(telegram_html, max_length)
    
    return messages


def _convert_tables_to_lists(html_content: str) -> str:
    """Convert HTML tables to Telegram-friendly list format.
    
    Args:
        html_content: HTML content with tables
        
    Returns:
        HTML content with tables converted to lists
    """
    # Pattern to match story table rows
    # Matches: <tr> with image in first td, content in second td
    story_pattern = r'<tr>\s*<td[^>]*>\s*<img[^>]*src="([^"]*)"[^>]*>\s*</td>\s*<td[^>]*>\s*(.*?)\s*</td>\s*</tr>'
    
    def replace_story(match):
        img_url = match.group(1)
        content = match.group(2)
        
        # Extract story title (first <strong><a> tag)
        title_match = re.search(r'<strong><a[^>]*href="([^"]*)"[^>]*>([^<]*)</a></strong>', content)
        if title_match:
            story_url = title_match.group(1)
            story_title = title_match.group(2)
        else:
            # Fallback: try to find any strong tag
            title_match = re.search(r'<strong>([^<]*)</strong>', content)
            if title_match:
                story_title = title_match.group(1)
                story_url = "#"
            else:
                story_title = "Story"
                story_url = "#"
        
        # Extract story number from title (e.g., "1. Story Title" -> "1")
        number_match = re.match(r'^(\d+)\.\s*(.*)', story_title)
        if number_match:
            story_num = number_match.group(1)
            story_title = number_match.group(2).strip()
        else:
            story_num = "?"
        
        # Extract source (second <a> tag, after the title)
        all_links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', content)
        source_text = ""
        source_url = ""
        if len(all_links) >= 2:
            # Second link is usually the source
            source_url = all_links[1][0]
            source_text = all_links[1][1]
        elif len(all_links) == 1:
            # Only one link, might be the source
            source_url = all_links[0][0]
            source_text = all_links[0][1]
        
        # Extract tags from span element
        tags_match = re.search(r'<span[^>]*>🏷️\s*(.*?)</span>', content, re.DOTALL)
        tags_html = ""
        if tags_match:
            # Extract individual tag links
            tag_links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', tags_match.group(1))
            if tag_links:
                tag_parts = []
                for url, text in tag_links:
                    tag_parts.append(f'<a href="{url}">{html.escape(text)}</a>')
                tags_html = "🏷️ " + " • ".join(tag_parts)
            else:
                # Fallback: extract plain text tags
                tags_text = re.sub(r'<[^>]+>', '', tags_match.group(1)).strip()
                if tags_text:
                    tags_html = f"🏷️ {html.escape(tags_text)}"
        
        # Extract comment and username
        comment_match = re.search(r'💬\s*<i>([^<]*)</i>\s*—\s*@([^<\s]*)', content)
        comment_html = ""
        if comment_match:
            comment_text = comment_match.group(1)
            username = comment_match.group(2)
            comment_html = f'<blockquote>💬 <i>{html.escape(comment_text)}</i> — @{html.escape(username)}</blockquote>'
        
        # Build Telegram-friendly format
        parts = []
        parts.append(f'<b>{story_num}. {html.escape(story_title)}</b>')
        
        if source_text:
            parts.append(f'Source: <a href="{source_url}">{html.escape(source_text)}</a>')
        
        if tags_html:
            parts.append(tags_html)
        
        if comment_html:
            parts.append(comment_html)
        
        return "\n".join(parts) + "\n"
    
    # Replace all story table rows
    html_content = re.sub(story_pattern, replace_story, html_content, flags=re.DOTALL)
    
    # Remove remaining table tags
    html_content = re.sub(r'<table[^>]*>', '', html_content)
    html_content = re.sub(r'</table>', '', html_content)
    html_content = re.sub(r'<tr[^>]*>', '', html_content)
    html_content = re.sub(r'</tr>', '', html_content)
    html_content = re.sub(r'<td[^>]*>', '', html_content)
    html_content = re.sub(r'</td>', '', html_content)
    
    # Convert headers to bold
    html_content = re.sub(r'<h([1-6])[^>]*>(.*?)</h[1-6]>', r'<b>\2</b>', html_content, flags=re.DOTALL)
    
    # Clean up extra whitespace
    html_content = re.sub(r'\n{3,}', '\n\n', html_content)
    
    return html_content


def _clean_telegram_html(html_content: str) -> str:
    """Clean HTML to use only Telegram-supported tags and escape entities.
    
    Args:
        html_content: HTML content to clean
        
    Returns:
        Cleaned HTML content with only Telegram-supported tags
    """
    # Remove unsupported tags but keep their content
    # Keep: b, strong, i, em, u, ins, s, strike, del, a, code, pre, blockquote, tg-spoiler
    # Remove: span, div, p, br (convert to newlines), img, style attributes
    
    # Convert <br> and <br/> to newlines
    html_content = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
    
    # Remove style attributes
    html_content = re.sub(r'\s+style="[^"]*"', '', html_content)
    
    # Remove img tags (Telegram doesn't support inline images in text messages)
    html_content = re.sub(r'<img[^>]*>', '', html_content, flags=re.IGNORECASE)
    
    # Replace <hr> and <hr/> tags with a visual separator (Telegram doesn't support hr)
    html_content = re.sub(r'<hr\s*/?>', '\n━━━━━━━━━━━━━━━━━━━━\n', html_content, flags=re.IGNORECASE)
    
    # Remove unsupported tags but keep content
    # Remove list tags (ul, ol, li) - convert to plain text with newlines
    html_content = re.sub(r'<ul[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</ul>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<ol[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</ol>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<li[^>]*>', '- ', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</li>', '\n', html_content, flags=re.IGNORECASE)
    
    # Remove other unsupported tags
    unsupported_tags = ['span', 'div', 'p', 'thead', 'tbody', 'th', 'td', 'tr', 'table']
    for tag in unsupported_tags:
        html_content = re.sub(f'<{tag}[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(f'</{tag}>', '', html_content, flags=re.IGNORECASE)
    
    # Escape HTML entities properly
    # Strategy: Protect supported tags, escape everything, then restore tags
    
    # Protect all supported tags (opening and closing) with placeholders
    tag_placeholders = {}
    tag_counter = 0
    
    # Pattern for opening tags: <tag> or <tag attr="value">
    # Pattern for closing tags: </tag>
    supported_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 
                      'code', 'pre', 'blockquote', 'tg-spoiler']
    
    def protect_tag(match):
        nonlocal tag_counter
        placeholder = f"__TAG_{tag_counter}__"
        tag_placeholders[placeholder] = match.group(0)
        tag_counter += 1
        return placeholder
    
    # Protect closing tags first
    for tag in supported_tags:
        pattern = f'</{tag}>'
        html_content = re.sub(pattern, protect_tag, html_content, flags=re.IGNORECASE)
    
    # Protect opening tags (without attributes for simple tags)
    for tag in supported_tags:
        pattern = f'<{tag}>'
        html_content = re.sub(pattern, protect_tag, html_content, flags=re.IGNORECASE)
    
    # Protect <a> tags separately (they have href attributes)
    a_tags = {}
    a_counter = 0
    
    def protect_a_tag(match):
        nonlocal a_counter
        placeholder = f"__A_OPEN_{a_counter}__"
        a_tags[placeholder] = match.group(1)  # Store href
        a_counter += 1
        return placeholder
    
    # Protect opening <a> tags
    html_content = re.sub(r'<a\s+href="([^"]*)"[^>]*>', protect_a_tag, html_content, flags=re.IGNORECASE)
    # Protect closing </a> tags
    html_content = re.sub(r'</a>', protect_tag, html_content, flags=re.IGNORECASE)
    
    # Now escape everything
    html_content = html.escape(html_content)
    
    # Restore protected tags (unescape them)
    for placeholder, original_tag in tag_placeholders.items():
        # The placeholder was escaped, so we need to find the escaped version
        escaped_placeholder = html.escape(placeholder)
        if escaped_placeholder in html_content:
            html_content = html_content.replace(escaped_placeholder, original_tag)
    
    for placeholder, href in a_tags.items():
        escaped_placeholder = html.escape(placeholder)
        if escaped_placeholder in html_content:
            # Unescape href if needed
            clean_href = href.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            html_content = html_content.replace(escaped_placeholder, f'<a href="{clean_href}">')
    
    # Clean up any escaped hr tags that might have slipped through after escaping
    html_content = re.sub(r'&lt;hr\s*/?&gt;', '\n━━━━━━━━━━━━━━━━━━━━\n', html_content, flags=re.IGNORECASE)
    
    # Clean up extra whitespace around separators
    html_content = re.sub(r'\n{3,}', '\n\n', html_content)
    
    return html_content


def _split_messages(content: str, max_length: int = 4096) -> List[str]:
    """Split content into multiple messages if it exceeds max_length.
    
    Args:
        content: HTML content to split
        max_length: Maximum length per message
        
    Returns:
        List of message strings
    """
    if len(content) <= max_length:
        return [content]
    
    messages = []
    current_message = ""
    
    # Split by double newlines (paragraph breaks) or story boundaries
    # Look for patterns like "<b>1. " or "<b>2. " which indicate new stories
    parts = re.split(r'(\n\n<b>\d+\.\s)', content)
    
    # Recombine parts, splitting when we exceed max_length
    for i, part in enumerate(parts):
        # If this part would exceed max_length, save current and start new
        if current_message and len(current_message) + len(part) > max_length - 100:  # 100 char buffer for part header
            messages.append(current_message.strip())
            current_message = part
        else:
            current_message += part
    
    # Add remaining content
    if current_message.strip():
        messages.append(current_message.strip())
    
    # If any message is still too long, split more aggressively
    final_messages = []
    for msg in messages:
        if len(msg) <= max_length:
            final_messages.append(msg)
        else:
            # Split by single newlines
            lines = msg.split('\n')
            current = ""
            for line in lines:
                if len(current) + len(line) + 1 > max_length:
                    if current:
                        final_messages.append(current.strip())
                    current = line + '\n'
                else:
                    current += line + '\n'
            if current.strip():
                final_messages.append(current.strip())
    
    return final_messages

