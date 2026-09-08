"""Regression coverage for the real mixed Markdown/HTML digest on X."""
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from post_x import _build_native_root, _native_text  # noqa: E402


def test_september_7_digest_preserves_stories_without_html():
    content = (ROOT / "writeup/2026/09/07/signals_2026-09-07.md").read_text()
    rendered = _build_native_root(datetime(2026, 9, 7), content, "Daily news.")
    assert "Swift’s Digital Ledger using tokenized deposits - Coindesk" in rendered
    assert "customer due diligence, transaction monitoring and staff training" in rendered
    assert "Governance • RedotPay • AML" in rendered
    assert "HYPE ($HYPE): BUY" in rendered
    assert not any(token in rendered for token in ("<div", "<a ", "href=", "style=", "<img", "https://", "**", "*Disclaimer"))


def test_inline_labels_entities_paragraphs_and_lists():
    raw = '## News\n\n<div><p>A <strong>Big Four</strong> firm &amp; B.</p><p>Next<br>line.</p></div>\n<ul><li>One</li><li>Two</li></ul>'
    result = _native_text(raw)
    assert "A Big Four firm & B." in result
    assert "Next\nline." in result
    assert "• One\n• Two" in result
    assert "firm & B.\n\nNext" in result


def test_drops_images_hidden_content_and_urls_but_retains_link_labels():
    raw = '![Cover](https://example.com/img)\n<script>bad()</script><style>css</style><p><a href="https://example.com/a(b)">Source</a> **[BTC](https://example.com/btc)** HTTPS://EXAMPLE.COM/x www.example.org example.com</p>'
    result = _native_text(raw)
    assert result == "Source BTC"


def test_numeric_comparisons_survive():
    assert _native_text("Volume < 3 and price > 2; return -0.83%.") == "Volume < 3 and price > 2; return -0.83%."


def test_empty_body_cannot_publish_just_a_masthead():
    with pytest.raises(ValueError, match="empty"):
        _build_native_root(datetime(2026, 9, 8), '<img src="a">', "intro")


def test_leftover_escaped_markup_is_held():
    with pytest.raises(ValueError, match="HTML"):
        _build_native_root(datetime(2026, 9, 8), '&amp;lt;div style="x"&amp;gt;body', "intro")
