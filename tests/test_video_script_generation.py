"""Tests for daily video-script generation and backfill helpers."""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        original_cwd = os.getcwd()
        os.chdir(temp_path)
        try:
            yield temp_path
        finally:
            os.chdir(original_cwd)


def test_script_prompt_is_registered():
    from squid_digest.context.prompts.template import (
        SCRIPT_MESSAGE,
        VIDEO_SCRIPT_INTRO,
        VIDEO_SCRIPT_OUTRO,
        get_script_system_message,
        prompts,
    )

    assert prompts["script"] == SCRIPT_MESSAGE
    assert VIDEO_SCRIPT_INTRO in get_script_system_message()
    assert VIDEO_SCRIPT_OUTRO in get_script_system_message()
    assert "{headlines}" in get_script_system_message()


def test_generate_video_script_writes_wrapped_markdown(temp_workspace):
    import digest

    target_date = datetime(2026, 4, 29)
    script_body = (
        f"{digest.VIDEO_SCRIPT_INTRO} First up, Bitcoin keeps setting the tone as "
        f"flows stay hot. Next, Pump.fun rewrites the revenue split after a large burn. "
        f"Meanwhile, Polymarket pushes back on breach claims and calls the data public. "
        f"And finally, regulators in Hong Kong are waving red flags at fake stablecoin "
        f"tickers. {digest.VIDEO_SCRIPT_OUTRO}"
    )

    mock_engine = MagicMock()
    mock_engine.generate_writeup_with_prompt = AsyncMock(return_value=script_body)

    result = asyncio.run(
        digest.generate_video_script(
            mock_engine,
            [
                "Pump.fun adjusts revenue split after burn",
                "Polymarket rejects breach claims",
            ],
            target_date,
            verbose=True,
        )
    )

    expected_path = Path("writeup/2026/04/29/video_script_2026-04-29.md")
    assert result == expected_path
    assert expected_path.exists()

    content = expected_path.read_text()
    assert content.startswith(
        "# 🎙️ SQUID Digest — Video Script — April 29, 2026\n"
        "> Draft — read time ≈ 1 min\n\n"
    )
    assert digest.VIDEO_SCRIPT_INTRO in content
    assert digest.VIDEO_SCRIPT_OUTRO in content

    kwargs = mock_engine.generate_writeup_with_prompt.await_args.kwargs
    assert kwargs["headlines"] == (
        "[1] Pump.fun adjusts revenue split after burn\n"
        "[2] Polymarket rejects breach claims"
    )
    assert kwargs["token_list"] == ""
    assert kwargs["prompt_type"] == "script"


def test_generate_video_script_failure_writes_diagnostic(temp_workspace):
    import digest

    target_date = datetime(2026, 4, 29)
    mock_engine = MagicMock()
    mock_engine.generate_writeup_with_prompt = AsyncMock(side_effect=RuntimeError("script boom"))

    result = asyncio.run(
        digest.generate_video_script(
            mock_engine,
            ["Pump.fun adjusts revenue split after burn"],
            target_date,
            verbose=True,
        )
    )

    assert result is None
    assert not Path("writeup/2026/04/29/video_script_2026-04-29.md").exists()

    diagnostic_path = Path("writeup/2026/04/29/diagnostic_video_script_2026-04-29.txt")
    assert diagnostic_path.exists()
    diagnostic_text = diagnostic_path.read_text()
    assert "script boom" in diagnostic_text
    assert "[1] Pump.fun adjusts revenue split after burn" in diagnostic_text


def test_extract_top_story_headlines_from_archived_signals():
    import backfill_video_scripts as backfill

    content = """## 🔥 Top Stories

<div style="border: 2px solid #FF6B35;">
  <p style="margin: 0 0 8px 0;">1. Pump.fun adjusts revenue split after burning supply - <a href="https://example.com"><strong>Coindesk</strong></a></p>
  <p style="margin: 0 0 8px 0;">2. Polymarket rejects breach claims and says the records were public - <a href="https://example.com"><strong>CoinTelegraph</strong></a></p>
</div>

## 🎯 Trading Signals
"""

    headlines = backfill.extract_top_story_headlines(content)
    assert headlines == [
        "Pump.fun adjusts revenue split after burning supply",
        "Polymarket rejects breach claims and says the records were public",
    ]


def test_load_headlines_for_date_uses_meta_fallback_when_parse_fails(temp_workspace):
    import backfill_video_scripts as backfill

    target_date = datetime(2026, 4, 28)
    signals_path = Path("writeup/2026/04/28/signals_2026-04-28.md")
    signals_path.parent.mkdir(parents=True, exist_ok=True)
    signals_path.write_text("## 🔥 Top Stories\n\n<div>No numbered stories here.</div>\n")

    meta_path = Path("writeup/2026/04/28/meta_2026-04-28.json")
    meta_path.write_text(
        json.dumps(
            {
                "top_story_headline": "Lead story recovered from meta",
                "blurb": "Fallback blurb recovered from meta",
            }
        )
    )

    headlines = backfill.load_headlines_for_date(target_date)
    assert headlines == [
        "Lead story recovered from meta",
        "Fallback blurb recovered from meta",
    ]


def test_find_recent_signal_dates_skips_missing_calendar_days(temp_workspace):
    import backfill_video_scripts as backfill

    for date_str in ["2026-04-29", "2026-04-27", "2026-04-26", "2026-04-25", "2026-04-24"]:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
        signals_path = Path(
            f"writeup/{target_date.strftime('%Y/%m/%d')}/signals_{date_str}.md"
        )
        signals_path.parent.mkdir(parents=True, exist_ok=True)
        signals_path.write_text("# stub\n")

    dates = backfill.find_recent_signal_dates(limit=5, writeup_dir=Path("writeup"))

    assert [date.strftime("%Y-%m-%d") for date in dates] == [
        "2026-04-29",
        "2026-04-27",
        "2026-04-26",
        "2026-04-25",
        "2026-04-24",
    ]
