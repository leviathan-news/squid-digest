#!/usr/bin/env python3
"""Validate Telegram HTML by checking tag nesting and order."""

import sys
import re
from typing import List, Tuple


def validate_telegram_html(html: str) -> Tuple[bool, List[str]]:
    """Validate Telegram HTML structure.
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Check tag balance
    open_i = html.count('<i>')
    close_i = html.count('</i>')
    open_b = html.count('<b>')
    close_b = html.count('</b>')
    open_blockquote = html.count('<blockquote>')
    close_blockquote = html.count('</blockquote>')
    
    if open_i != close_i:
        errors.append(f"<i> tags unbalanced: {open_i} open, {close_i} close")
    if open_b != close_b:
        errors.append(f"<b> tags unbalanced: {open_b} open, {close_b} close")
    if open_blockquote != close_blockquote:
        errors.append(f"<blockquote> tags unbalanced: {open_blockquote} open, {close_blockquote} close")
    
    # Check tag nesting order
    # Find all opening and closing tags with positions
    tags = []
    for m in re.finditer(r'<(/?)(blockquote|i|b)>', html):
        tags.append((m.start(), m.group(1) == '/', m.group(2)))
    
    # Check nesting: if we have <blockquote><i>, then </i> must come before </blockquote>
    stack = []
    for pos, is_closing, tag_name in tags:
        if not is_closing:
            stack.append((pos, tag_name))
        else:
            if not stack:
                errors.append(f"Closing tag </{tag_name}> at position {pos} has no matching opening tag")
            else:
                # Check if we're closing in the right order
                # The last opened tag should match this closing tag
                last_pos, last_tag = stack[-1]
                if last_tag != tag_name:
                    errors.append(
                        f"Tag nesting error at position {pos}: "
                        f"Expected </{last_tag}> but found </{tag_name}>. "
                        f"Last opened tag was <{last_tag}> at position {last_pos}"
                    )
                else:
                    stack.pop()
    
    if stack:
        for pos, tag_name in stack:
            errors.append(f"Unclosed tag <{tag_name}> at position {pos}")
    
    return len(errors) == 0, errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: validate_telegram_html.py <html_string>")
        sys.exit(1)
    
    html = sys.argv[1]
    is_valid, errors = validate_telegram_html(html)
    
    if is_valid:
        print("✓ HTML is valid")
        sys.exit(0)
    else:
        print("✗ HTML validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
