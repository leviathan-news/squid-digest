"""Bounded, weekday-balanced digest link experiment; dates are UTC."""
import hashlib
import os
from datetime import date, timedelta

EXPERIMENT = "digest-link-reply-20260908-v1"
START = date(2026, 9, 9)
END = START + timedelta(days=28)  # exclusive; normal linked replies resume
ARMS = ("linked_reply", "no_link")


def enabled() -> bool:
    return os.getenv("X_DIGEST_LINK_EXPERIMENT_ENABLED", "0").lower() in ("1", "true", "yes")


def assignment(day: date, meta: dict) -> dict:
    stored = meta.get("x_distribution")
    if stored:
        if stored.get("arm") not in ARMS:
            raise ValueError("unknown frozen X distribution arm")
        return stored
    # Existing roots predate assignment. Never retrofit an experiment onto
    # them or mistake an unfinished historical reply for a no-link treatment.
    experiment, arm = "", "linked_reply"
    if enabled() and not meta.get("tweet_id") and START <= day < END:
        experiment = EXPERIMENT
        week = (day - START).days // 7
        key = f"{EXPERIMENT}:{week // 2}:{day.weekday()}".encode()
        coin = hashlib.sha256(key).digest()[0] % 2
        arm = ARMS[coin ^ (week % 2)]
    return {"experiment": experiment, "arm": arm, "renderer": "native-html-v2"}
