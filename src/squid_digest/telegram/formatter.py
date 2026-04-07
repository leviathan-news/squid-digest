"""Formatter for converting digest content to Telegram-compatible HTML."""

import re
import html
from typing import List
import markdown2


def truncate_html_safely(html_content: str, max_length: int) -> str:
    """
    Truncate HTML content safely without breaking tags.

    Args:
        html_content: HTML content to truncate
        max_length: Maximum length in characters

    Returns:
        Truncated HTML with properly closed tags
    """
    if len(html_content) <= max_length:
        return html_content

    # Track open tags that need to be closed
    tag_stack = []

    # Regex to find HTML tags
    tag_pattern = re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)[^>]*>')

    # Find all tags and their positions
    truncated = html_content[:max_length]

    # Find the last complete position (before any broken tag)
    # Look for an incomplete tag at the end
    last_tag_start = truncated.rfind('<')
    if last_tag_start != -1 and '>' not in truncated[last_tag_start:]:
        # We have an incomplete tag, truncate before it
        truncated = truncated[:last_tag_start]

    # Now find all tags in the truncated content and track unclosed ones
    for match in tag_pattern.finditer(truncated):
        is_closing = match.group(1) == '/'
        tag_name = match.group(2).lower()

        # Skip self-closing tags
        if tag_name in ['br', 'img', 'hr', 'input', 'meta', 'link']:
            continue

        if is_closing:
            # Remove from stack if present
            if tag_stack and tag_stack[-1] == tag_name:
                tag_stack.pop()
        else:
            # Add to stack
            tag_stack.append(tag_name)

    # Close any remaining open tags in reverse order
    for tag_name in reversed(tag_stack):
        truncated += f'</{tag_name}>'

    # Add truncation indicator if we actually truncated
    if len(html_content) > max_length:
        truncated += '\n\n<i>[Message truncated...]</i>'

    return truncated


def format_for_telegram(markdown_content: str, max_length: int = 4096) -> List[str]:
    """Convert markdown digest content to Telegram-compatible HTML.
    
    Args:
        markdown_content: Raw markdown content from signals file
        max_length: Maximum message length (Telegram limit is 4096)
        
    Returns:
        List of formatted HTML messages (split if content exceeds max_length)
        
    Raises:
        ValueError: If markdown_content is not a string or max_length is invalid
        RuntimeError: If markdown conversion fails
    """
    # Validate input
    if not isinstance(markdown_content, str):
        raise ValueError(f"markdown_content must be a string, got {type(markdown_content).__name__}")
    
    if max_length <= 0:
        raise ValueError(f"max_length must be positive, got {max_length}")
    
    # Handle empty content
    if not markdown_content.strip():
        return [""]
    
    # Convert markdown to HTML first
    try:
        html_content = markdown2.markdown(
            markdown_content,
            extras=[
                'fenced-code-blocks',
                'tables',
                'header-ids'
            ]
        )
    except Exception as e:
        raise RuntimeError(f"Failed to convert markdown to HTML: {e}") from e
    
    # Validate HTML output
    if not isinstance(html_content, str):
        raise RuntimeError(f"markdown2.markdown() returned non-string: {type(html_content).__name__}")
    
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
    # Pattern to match story divs (new vertical format)
    # Matches: <div> with padding and border-bottom containing image and content
    # Also matches SQUID Pass divs with background-color: #FFF5F2
    story_pattern = r'<div[^>]*style="[^"]*padding:\s*16px[^"]*"[^>]*>\s*(?:<img[^>]*src="([^"]*)"[^>]*>)?\s*(.*?)\s*</div>'
    
    def replace_story(match):
        img_url = match.group(1)
        content = match.group(2)
        
        # Check if this is a SQUID Pass row (has h3 with "SQUID Pass Winner" or 🏆 emoji)
        if "SQUID Pass Winner" in content or ("🏆" in content and "<h3" in content):
            # Extract the full ad copy from the <p> tag.
            # Structure: <p>Ad copy text... - <a href="..."><strong>Source</strong></a></p>
            # We want the text before " - <a" as the headline, and the <a> as the source.
            p_match = re.search(r'<p[^>]*>(.*?)</p>', content, re.DOTALL)
            headline = ""
            source_url = "#"
            source_text = ""
            if p_match:
                p_content = p_match.group(1)
                # Split on " - <a" to separate ad copy from source link
                source_link_match = re.search(r'(.*?)\s*-\s*<a[^>]*href="([^"]*)"[^>]*>\s*<strong>([^<]*)</strong>\s*</a>', p_content, re.DOTALL)
                if source_link_match:
                    headline_raw = source_link_match.group(1)
                    source_url = source_link_match.group(2)
                    source_text = source_link_match.group(3)
                    # Strip HTML tags from headline, keep text
                    headline = re.sub(r'<[^>]+>', '', headline_raw).strip()
                else:
                    # Fallback: use the whole <p> text stripped of tags
                    headline = re.sub(r'<[^>]+>', '', p_content).strip()
            
            # Extract tags from <p> or <span> element
            tags_match = re.search(r'<p[^>]*>🏷️\s*(.*?)</p>', content, re.DOTALL)
            if not tags_match:
                tags_match = re.search(r'<span[^>]*>🏷️\s*(.*?)</span>', content, re.DOTALL)
            tags_html = ""
            if tags_match:
                # Extract individual tag links
                tag_links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', tags_match.group(1))
                if tag_links:
                    tag_parts = []
                    for url, text in tag_links:
                        text_clean = html.unescape(text)
                        tag_parts.append(f'<a href="{url}">{text_clean}</a>')
                    tags_html = "🏷️ " + " • ".join(tag_parts)
            
            # Extract comment and username (may be <a>@username</a> or bare @username)
            comment_match = re.search(r'💬\s*<i>(.*?)</i>\s*—\s*(?:<a[^>]*>)?@?([^<\s]*)(?:</a>)?', content, re.DOTALL)
            comment_html = ""
            if comment_match:
                comment_text = html.unescape(comment_match.group(1))
                username = html.unescape(comment_match.group(2))
                comment_text_clean = re.sub(r'<[^>]+>', '', comment_text)
                # Wrap @username in <a> tag to prevent Telegram from auto-linking as a Telegram mention
                profile_url = f"https://leviathannews.xyz/u/{username}/comments"
                comment_html = f'<blockquote>💬 <i>{comment_text_clean}</i> — <a href="{profile_url}">@{username}</a></blockquote>'
            else:
                # Comment without byline (anonymous author)
                comment_no_author = re.search(r'💬\s*<i>(.*?)</i>', content, re.DOTALL)
                if comment_no_author:
                    comment_text = html.unescape(comment_no_author.group(1))
                    comment_text_clean = re.sub(r'<[^>]+>', '', comment_text)
                    comment_html = f'<blockquote>💬 <i>{comment_text_clean}</i></blockquote>'

            # Build Telegram-friendly format for SQUID Pass
            parts = []
            parts.append('<b>🏆 SQUID Pass Winner</b>')
            
            if headline:
                headline_clean = html.unescape(headline)
                parts.append(headline_clean)
            
            if source_text:
                source_text_clean = html.unescape(source_text)
                parts.append(f'Source: <a href="{source_url}">{source_text_clean}</a>')
            
            if tags_html:
                parts.append(tags_html)
            
            if comment_html:
                parts.append(comment_html)
            
            return "\n".join(parts) + "\n"
        
        # Extract story headline and number from paragraph
        # New format: <p>1. Headline text - <a><strong>Source</strong></a></p>
        # Old format: "1. Headline text - <a><strong>Source</strong></a>"
        # Try to find paragraph with story number and headline
        p_match = re.search(r'<p[^>]*>(\d+)\.\s*([^<]+)\s*-\s*<a[^>]*href="([^"]*)"[^>]*><strong>([^<]+)</strong></a></p>', content)
        if p_match:
            story_num = p_match.group(1)
            story_title = p_match.group(2).strip()
            source_url = p_match.group(3)
            source_text = p_match.group(4).strip()
        else:
            # Fallback: extract from text before first <a> tag
            text_before_link = re.split(r'<a[^>]*>', content)[0]
            # Strip HTML tags from this text to get plain text
            text_clean = re.sub(r'<[^>]+>', '', text_before_link).strip()
            
            # Extract story number and title from the text
            # Format: "1. Headline text -" or "1. Headline text"
            number_match = re.match(r'^(\d+)\.\s*(.*?)(?:\s*-\s*)?$', text_clean)
            if number_match:
                story_num = number_match.group(1)
                story_title = number_match.group(2).strip()
                # Remove trailing dash if present
                story_title = re.sub(r'\s*-\s*$', '', story_title).strip()
            else:
                story_num = "?"
                story_title = text_clean if text_clean else "Story"
            
            # Extract source separately if not found in paragraph
            source_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>\s*<strong>([^<]*)</strong>\s*</a>', content)
            if source_match:
                source_url = source_match.group(1)
                source_text = source_match.group(2).strip()
            else:
                source_url = "#"
                source_text = ""
        
        # Extract tags from paragraph (new format) or span (old format)
        # New format: <p>🏷️ <a>tag1</a> • <a>tag2</a></p>
        # Old format: <span>🏷️ <a>tag1</a> • <a>tag2</a></span>
        tags_match = re.search(r'<p[^>]*>🏷️\s*(.*?)</p>', content, re.DOTALL)
        if not tags_match:
            tags_match = re.search(r'<span[^>]*>🏷️\s*(.*?)</span>', content, re.DOTALL)
        tags_html = ""
        if tags_match:
            # Extract individual tag links
            tag_links = re.findall(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', tags_match.group(1))
            if tag_links:
                tag_parts = []
                for url, text in tag_links:
                    # Unescape HTML entities - final escaping will happen in _clean_telegram_html
                    text_clean = html.unescape(text)
                    tag_parts.append(f'<a href="{url}">{text_clean}</a>')
                tags_html = "🏷️ " + " • ".join(tag_parts)
            else:
                # Fallback: extract plain text tags
                tags_text = re.sub(r'<[^>]+>', '', tags_match.group(1)).strip()
                if tags_text:
                    # Unescape HTML entities - final escaping will happen in _clean_telegram_html
                    tags_text_clean = html.unescape(tags_text)
                    tags_html = f"🏷️ {tags_text_clean}"

        # Extract comment and username
        # Pattern matches: <blockquote>💬 <i>comment</i> — <a>@username</a></blockquote>
        # or just: 💬 <i>comment</i> — <a>@username</a>
        comment_match = re.search(
            r'(?:<blockquote[^>]*>)?\s*💬\s*<i>(.*?)</i>\s*—\s*<a[^>]*href="[^"]*"[^>]*>@?([^<\s]*)</a>\s*(?:</blockquote>)?',
            content,
            re.DOTALL
        )
        comment_html = ""
        if comment_match:
            # Unescape HTML entities - final escaping will happen in _clean_telegram_html
            comment_text = html.unescape(comment_match.group(1))
            username = html.unescape(comment_match.group(2))
            # Clean up any nested HTML tags in comment text (strip them, keep text)
            # This prevents issues with nested <i> tags or other HTML
            comment_text_clean = re.sub(r'<[^>]+>', '', comment_text)
            # Wrap @username in <a> tag to prevent Telegram from auto-linking as a Telegram mention
            profile_url = f"https://leviathannews.xyz/u/{username}/comments"
            comment_html = f'<blockquote>💬 <i>{comment_text_clean}</i> — <a href="{profile_url}">@{username}</a></blockquote>'
        else:
            # Comment without byline (anonymous author)
            comment_no_author = re.search(
                r'(?:<blockquote[^>]*>)?\s*💬\s*<i>(.*?)</i>\s*(?:</blockquote>)?',
                content,
                re.DOTALL
            )
            if comment_no_author:
                comment_text = html.unescape(comment_no_author.group(1))
                comment_text_clean = re.sub(r'<[^>]+>', '', comment_text)
                comment_html = f'<blockquote>💬 <i>{comment_text_clean}</i></blockquote>'

        # Build Telegram-friendly format
        parts = []
        # Unescape HTML entities - final escaping will happen in _clean_telegram_html
        story_title_clean = html.unescape(story_title)
        parts.append(f'<b>{story_num}. {story_title_clean}</b>')

        if source_text:
            source_text_clean = html.unescape(source_text)
            parts.append(f'Source: <a href="{source_url}">{source_text_clean}</a>')
        
        if tags_html:
            parts.append(tags_html)
        
        if comment_html:
            parts.append(comment_html)
        
        return "\n".join(parts) + "\n"
    
    # Replace all story divs (including SQUID Pass)
    html_content = re.sub(story_pattern, replace_story, html_content, flags=re.DOTALL)
    
    # Remove remaining table tags (if any from old format)
    html_content = re.sub(r'<table[^>]*>', '', html_content)
    html_content = re.sub(r'</table>', '', html_content)
    html_content = re.sub(r'<tr[^>]*>', '', html_content)
    html_content = re.sub(r'</tr>', '', html_content)
    html_content = re.sub(r'<td[^>]*>', '', html_content)
    html_content = re.sub(r'</td>', '', html_content)
    
    # Convert headers to bold
    html_content = re.sub(r'<h([1-6])[^>]*>(.*?)</h[1-6]>', r'<b>\2</b>', html_content, flags=re.DOTALL)
    
    # Clean up extra whitespace (including around SQUID Pass section)
    # Remove multiple consecutive newlines
    html_content = re.sub(r'\n{3,}', '\n\n', html_content)
    # Remove leading/trailing whitespace from each line
    lines = html_content.split('\n')
    cleaned_lines = [line.rstrip() for line in lines]
    html_content = '\n'.join(cleaned_lines)
    # Remove multiple consecutive newlines again after line cleaning
    html_content = re.sub(r'\n{3,}', '\n\n', html_content)
    
    return html_content


def _clean_telegram_html(html_content: str) -> str:
    """Clean HTML to use only Telegram-supported tags and escape entities.

    Args:
        html_content: HTML content to clean

    Returns:
        Cleaned HTML content with only Telegram-supported tags
    """
    # First, unescape all HTML entities from markdown2 conversion
    # This prevents double-escaping (e.g., &quot; -> &amp;quot;)
    html_content = html.unescape(html_content)

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
    # Handle list items - first combine </li>\n<li> to avoid double newlines
    html_content = re.sub(r'</li>\s*<li[^>]*>', '\n• ', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'<li[^>]*>', '• ', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</li>', '\n', html_content, flags=re.IGNORECASE)

    # Convert literal "* " at start of lines to bullets (markdown2 doesn't always convert these)
    # This handles cases like "**Header:**\n* item" where the * isn't recognized as a list
    html_content = re.sub(r'^\* ', '• ', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'\n\* ', '\n• ', html_content)

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
    
    # Now escape everything (but not quotes - Telegram doesn't need them escaped)
    # quote=False means only escape &, <, > but not " and '
    html_content = html.escape(html_content, quote=False)
    
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
        List of message strings (all guaranteed to be <= max_length)
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
        # Check if adding this part would exceed max_length
        if current_message and len(current_message) + len(part) > max_length:
            # Check if we're in the middle of a blockquote
            blockquote_count = current_message.count('<blockquote>') - current_message.count('</blockquote>')
            
            # If we have an open blockquote, we need to find where it ends
            # Look ahead in the part to see if it contains the closing tag
            if blockquote_count > 0:
                # Check if the part contains the closing blockquote
                if '</blockquote>' in part:
                    # Include the part to complete the blockquote
                    current_message += part
                    # Now check if we still exceed max_length
                    if len(current_message) > max_length:
                        # We need to split, but first close tags properly in correct order
                        # Build tag stack to find correct closing order
                        tag_stack = []
                        for m in re.finditer(r'<(/?)(blockquote|i|b)>', current_message):
                            is_closing = m.group(1) == '/'
                            tag_name = m.group(2)
                            if not is_closing:
                                tag_stack.append(tag_name)
                            elif tag_stack and tag_stack[-1] == tag_name:
                                tag_stack.pop()
                        
                        # Find where to split - after all tags are closed
                        # Look for the last complete tag closure
                        split_point = len(current_message)
                        for i in range(len(current_message) - 1, -1, -1):
                            if current_message[i:].startswith('</blockquote>') or \
                               current_message[i:].startswith('</i>') or \
                               current_message[i:].startswith('</b>'):
                                # Check if this closes the last tag in stack
                                if tag_stack:
                                    # Find matching opening tag
                                    tag_name = current_message[i+2:current_message.find('>', i+2)]
                                    if tag_name in tag_stack:
                                        split_point = i + len(f'</{tag_name}>')
                                        break
                        
                        if split_point < len(current_message):
                            messages.append(current_message[:split_point].strip())
                            current_message = current_message[split_point:].strip()
                        else:
                            # Can't find good split point, close tags and split
                            closing_tags = []
                            for tag_name in reversed(tag_stack):
                                closing_tags.append(f'</{tag_name}>')
                            current_message += ''.join(closing_tags)
                            messages.append(current_message.strip())
                            current_message = part
                    else:
                        # Still fits, continue
                        continue
                else:
                    # Part doesn't contain closing tag, close tags in correct order and split
                    tag_stack = []
                    for m in re.finditer(r'<(/?)(blockquote|i|b)>', current_message):
                        is_closing = m.group(1) == '/'
                        tag_name = m.group(2)
                        if not is_closing:
                            tag_stack.append(tag_name)
                        elif tag_stack and tag_stack[-1] == tag_name:
                            tag_stack.pop()
                    closing_tags = []
                    for tag_name in reversed(tag_stack):
                        closing_tags.append(f'</{tag_name}>')
                    current_message += ''.join(closing_tags)
                    if current_message.strip():
                        messages.append(current_message.strip())
                    current_message = part
            else:
                # No open blockquote, safe to split
                if current_message.strip():
                    messages.append(current_message.strip())
                current_message = part
        else:
            current_message += part
    
    # Add remaining content
    if current_message.strip():
        messages.append(current_message.strip())
    
    # If any message is still too long, split more aggressively by lines
    final_messages = []
    for msg in messages:
        if len(msg) <= max_length:
            final_messages.append(msg)
        else:
            # Split by single newlines, but be careful about HTML tags
            lines = msg.split('\n')
            current = ""
            for line in lines:
                # Check if adding this line would exceed max_length
                line_with_newline = line + '\n'
                if len(current) + len(line_with_newline) > max_length:
                    # Before saving, ensure we close any open HTML tags
                    # IMPORTANT: Close tags in reverse order of opening (innermost first)
                    # Build a stack to track nesting order
                    tag_stack = []
                    for m in re.finditer(r'<(/?)(blockquote|i|b)>', current):
                        is_closing = m.group(1) == '/'
                        tag_name = m.group(2)
                        if not is_closing:
                            tag_stack.append(tag_name)
                        elif tag_stack and tag_stack[-1] == tag_name:
                            tag_stack.pop()
                    
                    # Close tags in reverse order (innermost first)
                    closing_tags = []
                    for tag_name in reversed(tag_stack):
                        closing_tags.append(f'</{tag_name}>')
                    current += ''.join(closing_tags)
                    
                    # Save current message if it's not empty
                    if current.strip():
                        final_messages.append(current.strip())
                    
                    # If the line itself is too long, split it by characters
                    if len(line) > max_length:
                        # Split long line into chunks
                        remaining = line
                        while len(remaining) > max_length:
                            final_messages.append(remaining[:max_length])
                            remaining = remaining[max_length:]
                        current = remaining + '\n'
                    else:
                        current = line_with_newline
                else:
                    current += line_with_newline
            
            # Add remaining content, ensuring tags are closed
            if current.strip():
                # Close any unclosed tags in correct nesting order
                tag_stack = []
                for m in re.finditer(r'<(/?)(blockquote|i|b)>', current):
                    is_closing = m.group(1) == '/'
                    tag_name = m.group(2)
                    if not is_closing:
                        tag_stack.append(tag_name)
                    elif tag_stack and tag_stack[-1] == tag_name:
                        tag_stack.pop()
                
                # Close tags in reverse order (innermost first)
                closing_tags = []
                for tag_name in reversed(tag_stack):
                    closing_tags.append(f'</{tag_name}>')
                current += ''.join(closing_tags)
                final_messages.append(current.strip())
    
    # Final safety check - ensure all messages are within limit and tags are balanced
    verified_messages = []
    for idx, msg in enumerate(final_messages):
        # Remove orphaned closing tags that don't have corresponding opening tags
        # This happens when we split messages in the middle of a blockquote/comment
        
        # For each closing tag, check if there's a corresponding opening tag before it
        # Remove closing tags that don't have matching opening tags
        i_positions = []
        for m in re.finditer(r'</i>', msg):
            i_positions.append(m.start())
        
        # Check each </i> tag - if there's no <i> before it in this message, remove it
        for i_pos in reversed(i_positions):  # Process from end to start to maintain positions
            # Check if there's an opening <i> tag before this closing tag
            text_before = msg[:i_pos]
            if '<i>' not in text_before or text_before.rfind('<i>') < text_before.rfind('</i>', 0, i_pos):
                # No opening tag before this closing tag, remove it
                msg = msg[:i_pos] + msg[i_pos+4:]
        
        # Same for blockquote tags
        blockquote_positions = []
        for m in re.finditer(r'</blockquote>', msg):
            blockquote_positions.append(m.start())
        
        for bq_pos in reversed(blockquote_positions):
            text_before = msg[:bq_pos]
            if '<blockquote>' not in text_before or text_before.rfind('<blockquote>') < text_before.rfind('</blockquote>', 0, bq_pos):
                msg = msg[:bq_pos] + msg[bq_pos+13:]
        
        # Same for <b> tags
        b_positions = []
        for m in re.finditer(r'</b>', msg):
            b_positions.append(m.start())
        
        for b_pos in reversed(b_positions):
            text_before = msg[:b_pos]
            if '<b>' not in text_before or text_before.rfind('<b>') < text_before.rfind('</b>', 0, b_pos):
                msg = msg[:b_pos] + msg[b_pos+4:]
        
        # Ensure tags are balanced (only close if we have more opens than closes)
        # IMPORTANT: Close tags in reverse order of opening (innermost first)
        # This ensures proper nesting: <blockquote><i>text</i></blockquote>
        blockquote_count = msg.count('<blockquote>') - msg.count('</blockquote>')
        i_count = msg.count('<i>') - msg.count('</i>')
        b_count = msg.count('<b>') - msg.count('</b>')
        
        # Build a stack of unclosed tags by scanning the message
        # This ensures we close tags in the correct nesting order
        tag_stack = []
        for m in re.finditer(r'<(/?)(blockquote|i|b)>', msg):
            is_closing = m.group(1) == '/'
            tag_name = m.group(2)
            
            if not is_closing:
                tag_stack.append(tag_name)
            else:
                # Remove matching opening tag from stack
                if tag_stack and tag_stack[-1] == tag_name:
                    tag_stack.pop()
                elif tag_name in tag_stack:
                    # Tag is in stack but not at top - this indicates nesting issue
                    # Remove it anyway to keep stack consistent
                    tag_stack.remove(tag_name)
        
        # Now close any remaining unclosed tags in reverse order (innermost first)
        closing_tags = []
        for tag_name in reversed(tag_stack):
            if tag_name == 'blockquote' and blockquote_count > 0:
                closing_tags.append('</blockquote>')
                blockquote_count -= 1
            elif tag_name == 'i' and i_count > 0:
                closing_tags.append('</i>')
                i_count -= 1
            elif tag_name == 'b' and b_count > 0:
                closing_tags.append('</b>')
                b_count -= 1
        
        # Add any remaining unclosed tags (fallback if stack method didn't catch them)
        if blockquote_count > 0:
            closing_tags.append('</blockquote>' * blockquote_count)
        if i_count > 0:
            closing_tags.append('</i>' * i_count)
        if b_count > 0:
            closing_tags.append('</b>' * b_count)
        
        msg += ''.join(closing_tags)
        
        # If we still have more closing tags than opening tags, remove excess from the end
        blockquote_close_excess = msg.count('</blockquote>') - msg.count('<blockquote>')
        i_close_excess = msg.count('</i>') - msg.count('<i>')
        b_close_excess = msg.count('</b>') - msg.count('<b>')
        
        # Remove excess closing tags from the end of the message
        if i_close_excess > 0:
            for _ in range(i_close_excess):
                msg = msg.rsplit('</i>', 1)[0]
        if blockquote_close_excess > 0:
            for _ in range(blockquote_close_excess):
                msg = msg.rsplit('</blockquote>', 1)[0]
        if b_close_excess > 0:
            for _ in range(b_close_excess):
                msg = msg.rsplit('</b>', 1)[0]
        
        if len(msg) <= max_length:
            verified_messages.append(msg)
        else:
            # Last resort: split by character chunks (this will break HTML, but better than failing)
            while len(msg) > max_length:
                verified_messages.append(msg[:max_length])
                msg = msg[max_length:]
            if msg:
                verified_messages.append(msg)
    
    return verified_messages

