# Ghost CMS Whitespace Rendering Guide

## The Problem

The Squid Digest was rendering with excessive whitespace in Ghost CMS, making the website and email versions look unprofessional:

- **Website**: No spacing before major section headers (Top Stories, Backtest Results, etc.) while sub-headers had inconsistent spacing
- **Email**: Excessive whitespace before headers and around the final horizontal rule, pushing the disclaimer far down the page
- **Root Cause**: Confusion about where whitespace control actually happens in the rendering pipeline

## The Key Learning: Where Whitespace Actually Gets Fixed

This is the critical insight that took most of the debugging time:

### ❌ NOT HERE: `scripts/digest.py`
The markdown generation script creates the raw content, but:
- Editing blank lines in the markdown doesn't control final rendering
- Ghost re-processes the markdown when displaying it
- Changes here affect internal markdown structure but not final visual spacing

### ❌ NOT HERE (Entirely): `src/squid_digest/backtest/newsletter_formatter.py`
The backtest formatting follows the same pattern as digest.py - it's just markdown generation.

### ✅ HERE: `src/squid_digest/email/ghost_client.py`
The ONLY place where you can reliably control final whitespace in Ghost is in the `_improve_html_formatting()` method:

```python
def _improve_html_formatting(self, html_content: str) -> str:
    """Post-process HTML for rendering in Ghost"""
    # This is where whitespace control actually happens
    # CSS styling, <br> removal/addition, all HTML cleanup
    return html_content
```

This method:
1. Takes markdown-to-HTML converted content
2. Applies regex transformations to fix spacing
3. Adds/removes `<br>` tags
4. **Adds CSS styling** (the actual solution!)
5. Converts to Ghost's mobiledoc format
6. Gets stored in Ghost and rendered on website/email

## The Solution: Use CSS, Not HTML Breaks

### Why `<br>` Tags Don't Work
- Email clients strip or ignore `<br>` tags inconsistently
- Ghost's mobiledoc conversion may lose them
- Different rendering between website and email versions

### Why CSS Margins Work
- CSS `margin-top` is more robust across email clients
- Preserved through Ghost's mobiledoc format
- Consistent rendering on both website and email
- Can be overridden by email client defaults (expected behavior)

## Implementation Details

### For Section Headers (Website + Email)
Add `margin-top` CSS directly to header tags:

```python
# Match header and add CSS margin
pattern = f'(\\s|<br\\s*/?>)*(<h[2-4])([^>]*?)>([^<]*?{header_name}[^<]*?)(</h[2-4]>)'

def add_margin(match):
    h_tag = match.group(2)
    attrs = match.group(3)
    content = match.group(4)
    close_tag = match.group(5)

    # Add margin-top CSS
    if 'style=' in attrs:
        # Prepend to existing style
        attrs = re.sub(r'style="([^"]*)"', r'style="margin-top: 10px; \1"', attrs)
    else:
        # Add new style attribute
        attrs = f'{attrs} style="margin-top: 10px;"'

    return f'{h_tag}{attrs}>{content}{close_tag}'
```

**Key Points:**
- Use `10px` for email compatibility (email clients may enlarge)
- Use `20px` for website-only styling if needed
- Always remove excessive whitespace before adding controlled margins
- Preserve existing style attributes when adding to them

### For Horizontal Rules (Email vs Website)
Remove excess whitespace around `<hr>` before disclaimer:

```python
# Strip excessive <br> and whitespace around HR
html_content = re.sub(
    r'(<br\s*/?>|\s)+(<hr[^>]*>)(\s*<br\s*/?>)*(?=\s*<p[^>]*>.*?Disclaimer)',
    r'\2',
    html_content,
    flags=re.IGNORECASE | re.DOTALL
)
```

Email clients add padding around block elements, so minimal HTML spacing is better.

## Debugging Checklist

When whitespace rendering is broken:

1. **Check ghost_client.py first** - 90% of whitespace issues are here
2. **Test with actual Ghost posts** - Create a test post and check the HTML in Ghost's API response
3. **Look at the mobiledoc HTML card** - The HTML is preserved as-is in the HTML card
4. **Use CSS instead of `<br>`** - CSS is more reliable across email clients
5. **Remember email client behavior** - Each email client renders CSS differently
   - Margins may be ignored or enlarged
   - `<br>` tags may be stripped
   - Padding is more reliable than margin in some clients

## Testing Approach

Don't rely on markdown changes showing up - actually test with Ghost:

1. Make changes to `_improve_html_formatting()` in ghost_client.py
2. Send a new digest with `python scripts/send_email.py --type public`
3. Check the created Ghost post in browser
4. Verify in Ghost's API that the HTML has your changes:

```python
from src.squid_digest.email.ghost_client import GhostEmailClient
client = GhostEmailClient()
response = client._make_request('GET', 'posts/', params={'limit': 1, 'include': 'mobiledoc'})
post = response['posts'][0]
# Check mobiledoc['cards'][0][1]['html'] for your CSS changes
```

## Common Mistakes

1. **Editing digest.py expecting it to change website rendering** - The markdown generation is separate from HTML rendering
2. **Using `<br>` tags for spacing** - Use CSS margins instead
3. **Forgetting email client limitations** - CSS margins work but may be reduced by client padding
4. **Not checking actual Ghost HTML** - Always verify your changes made it into the mobiledoc
5. **Assuming website rendering = email rendering** - They're different and respond differently to styling

## Summary

- **Whitespace rendering in Ghost = HTML post-processing in `ghost_client.py`**
- **Use CSS `margin-top` for reliable, consistent spacing**
- **Email clients are the constraint - test both website and email**
- **Always verify changes in Ghost's API, not just the markdown source**

