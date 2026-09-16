import sys
from pathlib import Path
from unittest.mock import MagicMock

import requests
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from squid_digest.x.client import XAPIError, XClient
from post_x import _format_x_failure


def _client(monkeypatch):
    for key in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(key, "test")
    session = MagicMock()
    monkeypatch.setattr("squid_digest.x.client.OAuth1Session", lambda *args, **kwargs: session)
    return XClient(), session


def test_post_error_projects_x_reason_without_echoing_sensitive_values(monkeypatch):
    client, session = _client(monkeypatch)
    response = MagicMock(status_code=403)
    response.json.return_value = {
        "title": "Client Forbidden",
        "detail": (
            "Authorization: Bearer abcSECRET123; "
            "access_token=do-not-log-this-value; app cannot post"
        ),
        "type": "https://api.x.com/2/problems/client-forbidden",
    }
    response.raise_for_status.side_effect = requests.HTTPError("403")
    session.post.return_value = response

    with pytest.raises(XAPIError) as raised:
        client.post_tweet("safe text")

    assert raised.value.diagnostic["status"] == 403
    assert raised.value.diagnostic["title"] == "Client Forbidden"
    assert "abcSECRET123" not in str(raised.value.diagnostic)
    assert "do-not-log-this-value" not in str(raised.value.diagnostic)
    assert "[REDACTED]" in raised.value.diagnostic["detail"]


def test_read_only_identity_diagnostic_does_not_post(monkeypatch):
    client, session = _client(monkeypatch)
    response = MagicMock(status_code=200, ok=True)
    response.json.return_value = {"data": {"id": "42", "username": "leviathan_news"}}
    session.get.return_value = response

    result = client.diagnose_authenticated_user()

    assert result == {
        "ok": True,
        "operation": "get_authenticated_user",
        "status": 200,
        "account": {"id": "42", "username": "leviathan_news"},
    }
    session.post.assert_not_called()
    assert session.get.call_args.args[0].endswith("/users/me")


def test_read_only_identity_diagnostic_returns_redacted_403(monkeypatch):
    client, session = _client(monkeypatch)
    response = MagicMock(status_code=403, ok=False)
    response.json.return_value = {
        "title": "Forbidden",
        "detail": "bearer token-secret-value is not permitted",
        "code": 403,
    }
    session.get.return_value = response

    result = client.diagnose_authenticated_user()

    assert result["ok"] is False
    assert result["status"] == 403
    assert result["title"] == "Forbidden"
    assert result["code"] == "403"
    assert "token-secret-value" not in str(result)
    session.post.assert_not_called()


def test_post_runner_logs_only_the_projected_provider_failure():
    failure = XAPIError(
        "post_tweet",
        {"status": 403, "title": "Client Forbidden", "detail": "write access unavailable"},
    )

    assert _format_x_failure(failure) == (
        '{"detail": "write access unavailable", "status": 403, '
        '"title": "Client Forbidden"}'
    )
