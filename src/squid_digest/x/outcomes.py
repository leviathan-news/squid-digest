"""One-shot, actual-age outcome snapshots for the digest link experiment."""
from __future__ import annotations

import json
import fcntl
import os
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from squid_digest import config
from squid_digest.x.policy import ARMS, EXPERIMENT

MIN_AGE_HOURS = 24
NOMINAL_MAX_AGE_HOURS = 30
MAX_DIGESTS_PER_RUN = 2
ESTIMATED_READ_MDOLLARS_PER_POST = 5
PUBLIC_KEYS = (
    "impression_count", "like_count", "retweet_count", "reply_count",
    "quote_count", "bookmark_count",
)
PRIVATE_KEYS = ("engagements", "user_profile_clicks", "url_link_clicks", "impression_count")


@dataclass(frozen=True)
class DueDigest:
    day: datetime
    path: Path
    meta: dict
    age_hours: float


@contextmanager
def collection_lock():
    """Serialize paid collectors that share this checkout's metadata."""
    config.WRITEUP_DIR.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(config.WRITEUP_DIR, os.O_RDONLY)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another X outcome collector owns this checkout") from exc
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


def due_digests(now: datetime, *, max_digests: int = MAX_DIGESTS_PER_RUN) -> list[DueDigest]:
    now = now.astimezone(timezone.utc)
    due = []
    for path in sorted(config.WRITEUP_DIR.glob("????/??/??/meta_????-??-??.json")):
        try:
            meta = json.loads(path.read_text())
            state = meta.get("x_distribution") or {}
            posted_at = _parse_time(state["root_posted_at"])
            day = datetime.strptime(path.stem.removeprefix("meta_"), "%Y-%m-%d")
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
        age = (now - posted_at).total_seconds() / 3600
        if (
            state.get("experiment") == EXPERIMENT
            and state.get("arm") in ARMS
            and state.get("root_state") == "confirmed"
            and not state.get("outcome")
            and age >= MIN_AGE_HOURS
        ):
            due.append(DueDigest(day, path, meta, age))
    return due[:max_digests]


def _metrics(row: dict) -> dict:
    public = row.get("public_metrics") or {}
    private = row.get("non_public_metrics") or {}
    organic = row.get("organic_metrics") or {}
    result = {key: int(public.get(key) or 0) for key in PUBLIC_KEYS}
    for key in PRIVATE_KEYS:
        result[key] = int(private.get(key) or organic.get(key) or result.get(key) or 0)
    return result


def collect(client, now: datetime, *, max_digests: int = MAX_DIGESTS_PER_RUN) -> list[dict]:
    """Read every due root/reply once, then atomically persist complete snapshots."""
    candidates = due_digests(now, max_digests=max_digests)
    ids = []
    for candidate in candidates:
        ids.append(str(candidate.meta["tweet_id"]))
        reply_id = candidate.meta.get("tweet_reply_id")
        if reply_id:
            ids.append(str(reply_id))
    if not ids:
        return []
    rows = {str(row.get("id")): row for row in client.get_posts(ids)}
    missing_first_read = [value for value in ids if value not in rows]
    if missing_first_read:
        # One immediate bounded retry handles a transient partial batch. A
        # second omission is frozen as unavailable so it cannot bill forever.
        rows.update({
            str(row.get("id")): row for row in client.get_posts(missing_first_read)
        })
    results = []
    measured_at = now.astimezone(timezone.utc).isoformat()
    for candidate in candidates:
        state = candidate.meta["x_distribution"]
        root_id = str(candidate.meta["tweet_id"])
        reply_id = candidate.meta.get("tweet_reply_id")
        resources = 1 + int(bool(reply_id))
        candidate_ids = {root_id, str(reply_id) if reply_id else None}
        retry_resources = len(candidate_ids.intersection(missing_first_read))
        missing = [value for value in (root_id, str(reply_id) if reply_id else None) if value and value not in rows]
        outcome = {
            "status": "unavailable" if missing else "collected",
            "measured_at": measured_at,
            "actual_age_hours": round(candidate.age_hours, 3),
            "timing": "nominal_24h" if candidate.age_hours <= NOMINAL_MAX_AGE_HOURS else "late_current_total",
            "measurement_basis": "current_cumulative_x_snapshot",
            "root_metrics": _metrics(rows[root_id]) if root_id in rows else None,
            "reply_metrics": _metrics(rows[str(reply_id)]) if reply_id and str(reply_id) in rows else None,
            "missing_post_ids": missing,
            "api_resources_read": resources + retry_resources,
            "estimated_read_mdollars": (
                resources + retry_resources
            ) * ESTIMATED_READ_MDOLLARS_PER_POST,
            "cost_basis": "estimated_mdollars_not_vendor_billing",
        }
        state["outcome"] = outcome
        config.save_meta(candidate.day, {"x_distribution": state})
        results.append({"date": candidate.day.date().isoformat(), "arm": state["arm"], **outcome})
    return results


def _rate(numerator: int, denominator: int):
    return numerator / denominator if denominator else None


def report() -> dict:
    arms = {arm: [] for arm in ARMS}
    late = 0
    for path in sorted(config.WRITEUP_DIR.glob("????/??/??/meta_????-??-??.json")):
        try:
            state = json.loads(path.read_text()).get("x_distribution") or {}
        except (OSError, json.JSONDecodeError):
            continue
        outcome = state.get("outcome")
        if state.get("experiment") == EXPERIMENT and state.get("arm") in arms and outcome:
            arms[state["arm"]].append(outcome)
            late += int(outcome.get("timing") != "nominal_24h")
    summaries = {}
    for arm, rows in arms.items():
        root = [
            row["root_metrics"] for row in rows
            if row.get("timing") == "nominal_24h" and row.get("status") == "collected"
        ]
        impressions = sum(row["impression_count"] for row in root)
        profile_clicks = sum(row["user_profile_clicks"] for row in root)
        reposts_quotes = sum(row["retweet_count"] + row["quote_count"] for row in root)
        engagements = sum(row["engagements"] for row in root)
        summaries[arm] = {
            "n_nominal": len(root), "n_all": len(rows), "root_impressions": impressions,
            "profile_clicks": profile_clicks,
            "profile_click_rate": _rate(profile_clicks, impressions),
            "repost_quote_rate": _rate(reposts_quotes, impressions),
            "engagement_rate": _rate(engagements, impressions),
            "reply_url_clicks": sum(
                int((row.get("reply_metrics") or {}).get("url_link_clicks") or 0) for row in rows
            ),
        }
    return {
        "experiment": EXPERIMENT, "arms": summaries, "late_snapshots": late,
        "interpretation": (
            "Descriptive root-post comparison. X does not expose copy-link actions or follows per post; "
            "profile clicks and reposts/quotes are the direct growth proxies. Late snapshots are excluded from rates."
        ),
    }
