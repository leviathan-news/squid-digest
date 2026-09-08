"""No-link completion and resume semantics, with every X call mocked."""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from squid_digest import config
from squid_digest.x.policy import START, assignment
import post_x


@pytest.fixture
def delivery(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WRITEUP_DIR", tmp_path)
    monkeypatch.setenv("X_DIGEST_LINK_EXPERIMENT_ENABLED", "1")
    for key in ('X_API_KEY', 'X_API_SECRET', 'X_ACCESS_TOKEN', 'X_ACCESS_TOKEN_SECRET', 'X_ACCOUNT_USERNAME'):
        monkeypatch.setenv(key, 'test')
    client = MagicMock()
    client.search_recent.return_value = []
    client.post_tweet.side_effect = [{'data': {'id': 'root'}}, {'data': {'id': 'reply'}}]
    monkeypatch.setattr('squid_digest.x.XClient', lambda: client)

    def setup(arm):
        day = next(START + timedelta(days=i) for i in range(14) if assignment(START + timedelta(days=i), {})['arm'] == arm)
        date = datetime.combine(day, datetime.min.time())
        config.get_writeup_file_path(f'signals_{day.isoformat()}.md', date).write_text('<p>Complete <b>digest</b> body.</p>')
        config.save_meta(date, {'blurb': "In today's digest: Broken frag", 'top_story_headline': 'Complete leading headline'})
        monkeypatch.setattr(sys, 'argv', ['post_x.py', '--date', day.isoformat()])
        return date

    return setup, client


def test_no_link_arm_never_searches_or_posts_a_reply_and_rerun_is_free(delivery):
    setup, client = delivery
    date = setup('no_link')
    post_x.main()
    assert client.post_tweet.call_count == 1
    assert client.search_recent.call_count == 1
    assert 'Complete leading headline' in client.post_tweet.call_args.args[0]
    assert 'Broken frag' not in client.post_tweet.call_args.args[0]
    meta = config.load_meta(date)
    assert meta['tweet_status'] == 'ok'
    assert meta['x_distribution']['reply_state'] == 'not_applicable'
    assert 'tweet_reply_id' not in meta
    client.reset_mock()
    post_x.main()
    client.post_tweet.assert_not_called()
    client.search_recent.assert_not_called()


def test_linked_arm_posts_full_root_and_one_reply(delivery):
    setup, client = delivery
    date = setup('linked_reply')
    post_x.main()
    assert client.post_tweet.call_count == 2
    assert client.post_tweet.call_args.kwargs == {'in_reply_to_tweet_id': 'root'}
    assert config.load_meta(date)['x_distribution']['estimated_delivery_mdollars'] == 215


def test_ambiguous_create_is_never_blindly_replayed_even_with_force(delivery, monkeypatch):
    setup, client = delivery
    date = setup('no_link')
    client.post_tweet.side_effect = TimeoutError('unknown')
    with pytest.raises(SystemExit):
        post_x.main()
    assert config.load_meta(date)['x_distribution']['root_state'] == 'unknown'
    client.reset_mock()
    monkeypatch.setattr(sys, 'argv', [*sys.argv, '--force'])
    with pytest.raises(RuntimeError, match='unproven'):
        post_x.main()
    client.post_tweet.assert_not_called()


def test_dry_run_does_not_assign_or_send(delivery, monkeypatch):
    setup, client = delivery
    date = setup('no_link')
    monkeypatch.setattr(sys, 'argv', [*sys.argv, '--dry-run'])
    before = config.load_meta(date)
    post_x.main()
    assert config.load_meta(date) == before
    client.post_tweet.assert_not_called()
    client.search_recent.assert_not_called()
