import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from squid_digest import config
from squid_digest.x.outcomes import collect, due_digests, report
from squid_digest.x.policy import EXPERIMENT


NOW = datetime(2026, 9, 12, 16, tzinfo=timezone.utc)


class Client:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get_posts(self, ids):
        self.calls.append(ids)
        return [self.rows[value] for value in ids if value in self.rows]


def _record(day, arm, posted_at, *, reply=True):
    meta = {
        "tweet_id": f"root-{day.day}",
        "tweet_status": "ok",
        "x_distribution": {
            "experiment": EXPERIMENT,
            "arm": arm,
            "root_state": "confirmed",
            "root_posted_at": posted_at.isoformat(),
        },
    }
    if reply:
        meta["tweet_reply_id"] = f"reply-{day.day}"
    config.save_meta(day, meta)


def _row(post_id, impressions, *, profiles=0, clicks=0, reposts=0, quotes=0):
    return {
        "id": post_id,
        "public_metrics": {
            "impression_count": impressions, "like_count": 3,
            "retweet_count": reposts, "reply_count": 1, "quote_count": quotes,
            "bookmark_count": 2,
        },
        "non_public_metrics": {
            "engagements": 9, "user_profile_clicks": profiles,
            "url_link_clicks": clicks, "impression_count": impressions,
        },
    }


def test_collects_complete_exact_age_snapshots_once(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WRITEUP_DIR", tmp_path)
    linked = datetime(2026, 9, 10)
    no_link = datetime(2026, 9, 11)
    _record(linked, "linked_reply", NOW - timedelta(hours=25), reply=True)
    _record(no_link, "no_link", NOW - timedelta(hours=24), reply=False)
    rows = {
        "root-10": _row("root-10", 100, profiles=5, reposts=2, quotes=1),
        "reply-10": _row("reply-10", 20, clicks=4),
        "root-11": _row("root-11", 200, profiles=12, reposts=5),
    }
    client = Client(rows)
    results = collect(client, NOW)
    assert len(results) == 2
    assert client.calls == [["root-10", "reply-10", "root-11"]]
    linked_meta = config.load_meta(linked)["x_distribution"]["outcome"]
    assert linked_meta["actual_age_hours"] == 25
    assert linked_meta["timing"] == "nominal_24h"
    assert linked_meta["reply_metrics"]["url_link_clicks"] == 4
    assert linked_meta["estimated_read_mdollars"] == 10
    assert collect(client, NOW + timedelta(hours=1)) == []
    assert len(client.calls) == 1

    summary = report()
    assert summary["arms"]["linked_reply"]["profile_click_rate"] == 0.05
    assert summary["arms"]["linked_reply"]["repost_quote_rate"] == 0.03
    assert summary["arms"]["no_link"]["profile_click_rate"] == 0.06
    assert summary["arms"]["linked_reply"]["reply_url_clicks"] == 4


def test_too_early_waits_and_late_snapshot_is_labelled_and_excluded(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WRITEUP_DIR", tmp_path)
    early = datetime(2026, 9, 10)
    late = datetime(2026, 9, 11)
    _record(early, "no_link", NOW - timedelta(hours=23, minutes=59), reply=False)
    _record(late, "no_link", NOW - timedelta(hours=31), reply=False)
    assert [row.day for row in due_digests(NOW)] == [late]
    client = Client({"root-11": _row("root-11", 100, profiles=10)})
    assert collect(client, NOW)[0]["timing"] == "late_current_total"
    summary = report()
    assert summary["late_snapshots"] == 1
    assert summary["arms"]["no_link"]["n_all"] == 1
    assert summary["arms"]["no_link"]["n_nominal"] == 0
    assert summary["arms"]["no_link"]["profile_click_rate"] is None


def test_missing_reply_gets_one_bounded_retry_then_becomes_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WRITEUP_DIR", tmp_path)
    day = datetime(2026, 9, 10)
    _record(day, "linked_reply", NOW - timedelta(hours=24), reply=True)
    client = Client({"root-10": _row("root-10", 100)})
    result = collect(client, NOW)
    assert result[0]["status"] == "unavailable"
    assert client.calls == [["root-10", "reply-10"], ["reply-10"]]
    outcome = config.load_meta(day)["x_distribution"]["outcome"]
    assert outcome["missing_post_ids"] == ["reply-10"]
    assert outcome["api_resources_read"] == 3
    assert collect(client, NOW + timedelta(days=1)) == []


def test_transient_partial_batch_is_recovered_once(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WRITEUP_DIR", tmp_path)
    day = datetime(2026, 9, 10)
    _record(day, "linked_reply", NOW - timedelta(hours=24), reply=True)

    class PartialClient(Client):
        def get_posts(self, ids):
            self.calls.append(ids)
            if len(self.calls) == 1:
                return [self.rows["root-10"]]
            return [self.rows[value] for value in ids]

    client = PartialClient({
        "root-10": _row("root-10", 100),
        "reply-10": _row("reply-10", 20, clicks=3),
    })
    result = collect(client, NOW)
    assert result[0]["status"] == "collected"
    assert result[0]["reply_metrics"]["url_link_clicks"] == 3
    assert result[0]["api_resources_read"] == 3


def test_client_requests_only_metrics_fields(monkeypatch):
    from unittest.mock import MagicMock, patch
    from squid_digest.x.client import XClient

    for key in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(key, "test")
    response = MagicMock()
    response.json.return_value = {"data": [{"id": "1"}]}
    with patch("squid_digest.x.client.OAuth1Session") as factory:
        factory.return_value.get.return_value = response
        assert XClient().get_posts(["1"]) == [{"id": "1"}]
    kwargs = factory.return_value.get.call_args.kwargs
    assert kwargs["params"]["ids"] == "1"
    assert "non_public_metrics" in kwargs["params"]["tweet.fields"]
    assert kwargs["timeout"] == 30
