"""Deterministic plain-text rendering for mixed HTML/Markdown digest bodies."""
import re
from html import unescape

from bs4 import BeautifulSoup, Comment

# Include bare domains: X can turn these into billable links too.
URL = re.compile(r"(?:https?://|www\.)\S+|\b(?:[a-z0-9-]+\.)+[a-z]{2,63}(?:[/?:#]\S*)?", re.I)
HTML_REMNANT = re.compile(r"</?[a-z][^>]*>|\b(?:href|src|style)\s*=", re.I)
MARKDOWN_REMNANT = re.compile(r"!\[|\]\(")


def _html_text(fragment: str) -> str:
    soup = BeautifulSoup(fragment, "html.parser")
    for node in soup.find_all(string=lambda value: isinstance(value, Comment)):
        node.extract()
    for node in soup.find_all(["script", "style", "noscript", "template", "img", "svg"]):
        node.decompose()
    for node in soup.find_all("br"):
        node.replace_with("\n")
    for node in soup.find_all("li"):
        node.insert_before("\n• ")
        node.append("\n")
    for node in soup.find_all(["p", "div", "section", "article", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table"]):
        node.insert_before("\n\n")
        node.append("\n\n")
    for node in soup.find_all("tr"):
        node.append("\n")
    for node in soup.find_all(["td", "th"]):
        node.append(" | ")
    return soup.get_text()


def _markdown_links(text: str) -> str:
    """Flatten inline links/images, including URLs with balanced parentheses."""
    output = []
    cursor = 0
    while cursor < len(text):
        start = text.find("[", cursor)
        if start < 0:
            output.append(text[cursor:])
            break
        image = start > 0 and text[start - 1] == "!"
        label_end = text.find("](", start + 1)
        if label_end < 0:
            output.append(text[cursor:])
            break
        depth = 1
        end = label_end + 2
        while end < len(text) and depth:
            if text[end] == "(":
                depth += 1
            elif text[end] == ")":
                depth -= 1
            end += 1
        if depth:
            output.append(text[cursor:])
            break
        output.append(text[cursor:start - int(image)])
        if not image:
            output.append(text[start + 1:label_end])
        cursor = end
    return "".join(output)


def native_text(content: str) -> str:
    # Parse attributes BEFORE removing URLs. Removing an href's URL first is
    # what leaked broken <a href=" fragments into the September 7 X post.
    text = _html_text(str(content or ""))
    text = _markdown_links(text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = text.replace("*", "").replace("__", "").replace("`", "").replace("~~", "")
    if HTML_REMNANT.search(unescape(text)):
        raise ValueError("native digest contains unconverted HTML")
    if MARKDOWN_REMNANT.search(text):
        raise ValueError("native digest contains unconverted Markdown links")
    text = URL.sub("", text)
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.splitlines()]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return re.sub(r"(?m)^(• [^\n]+)\n\n(?=• )", r"\1\n", text)
