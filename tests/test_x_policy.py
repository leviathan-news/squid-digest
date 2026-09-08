import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from squid_digest.x.policy import ARMS, END, EXPERIMENT, START, assignment


def test_balanced_weekdays_in_each_fortnight_and_bounded_expiry(monkeypatch):
    monkeypatch.setenv("X_DIGEST_LINK_EXPERIMENT_ENABLED", "1")
    for offset in (0, 14):
        days = [START + timedelta(days=i + offset) for i in range(14)]
        for weekday in range(7):
            assert {assignment(d, {})["arm"] for d in days if d.weekday() == weekday} == set(ARMS)
    assert assignment(START - timedelta(days=1), {})["experiment"] == ""
    assert assignment(END, {})["arm"] == "linked_reply"
    assert assignment(END, {})["experiment"] == ""


def test_legacy_roots_and_frozen_assignments_never_switch(monkeypatch):
    monkeypatch.setenv("X_DIGEST_LINK_EXPERIMENT_ENABLED", "1")
    assert assignment(START, {"tweet_id": "old"})["experiment"] == ""
    frozen = {"experiment": EXPERIMENT, "arm": "no_link", "root_state": "confirmed"}
    assert assignment(END, {"x_distribution": frozen}) == frozen


def test_experiment_is_default_off(monkeypatch):
    monkeypatch.delenv("X_DIGEST_LINK_EXPERIMENT_ENABLED", raising=False)
    assert assignment(START, {})["experiment"] == ""
