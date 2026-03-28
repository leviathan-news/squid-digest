"""
Tests for sentiment state tracking.

These tests verify:
1. Decay math is correct (uses HALF_LIFE_DAYS from SentimentTracker)
2. Signal spikes are applied correctly
3. Ranking and candidate selection work
4. State persistence works
5. Edge cases are handled
"""

import pytest
import tempfile
import json
import math
from pathlib import Path
from datetime import date, timedelta
from dataclasses import dataclass

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.backtest.sentiment_state import SentimentTracker, TokenSentiment

# Use the actual half-life from the tracker so tests stay in sync
HALF_LIFE = SentimentTracker.HALF_LIFE_DAYS


@dataclass
class MockSignal:
    """Mock signal for testing."""
    symbol: str
    signal_type: str
    token_name: str = ""


class TestSentimentDecay:
    """Tests for decay calculation."""

    def test_no_decay_same_day(self):
        """No decay should be applied on the same day."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")

            # Add a signal
            today = date.today()
            tracker.apply_signal("BTC", "STRONG BUY", today)

            # Apply decay for same day
            decay = tracker.apply_decay(today)

            assert decay == {}, "No decay should be applied on same day"
            assert tracker.sentiments["BTC"].score == 3.0

    def test_half_decay_after_one_half_life(self):
        """Score should be halved after exactly one half-life period."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")

            day_0 = date(2025, 1, 1)
            day_hl = day_0 + timedelta(days=int(HALF_LIFE))

            tracker.apply_signal("BTC", "BUY", day_0)
            assert tracker.sentiments["BTC"].score == 2.0

            tracker.apply_decay(day_hl)
            final_score = tracker.sentiments["BTC"].score

            assert abs(final_score - 1.0) < 0.01, f"Expected ~1.0, got {final_score}"

    def test_quarter_decay_after_two_half_lives(self):
        """Score should be quartered after two half-life periods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")

            day_0 = date(2025, 1, 1)
            day_2hl = day_0 + timedelta(days=int(HALF_LIFE * 2))

            tracker.apply_signal("BTC", "BUY", day_0)

            tracker.apply_decay(day_2hl)
            final_score = tracker.sentiments["BTC"].score

            assert abs(final_score - 0.5) < 0.01, f"Expected ~0.5, got {final_score}"

    def test_decay_zeroes_small_values(self):
        """Very small values should be zeroed to avoid noise."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")

            day_0 = date(2025, 1, 1)
            # Use enough half-lives to drive score below threshold
            day_far = day_0 + timedelta(days=int(HALF_LIFE * 10))

            tracker.apply_signal("BTC", "WEAK BUY", day_0)  # +1.0

            tracker.apply_decay(day_far)

            assert tracker.sentiments["BTC"].score == 0.0

    def test_decay_preserves_sign(self):
        """Decay should preserve positive/negative sign."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")

            day_0 = date(2025, 1, 1)
            day_hl = day_0 + timedelta(days=int(HALF_LIFE))

            tracker.apply_signal("BTC", "SELL", day_0)  # -2.0

            tracker.apply_decay(day_hl)

            assert tracker.sentiments["BTC"].score < 0
            assert abs(tracker.sentiments["BTC"].score - (-1.0)) < 0.01


class TestSignalSpikes:
    """Tests for signal spike application."""

    def test_spike_weights(self):
        """Verify correct spike weights for each signal type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            test_cases = [
                ("A", "STRONG BUY", 3.0),
                ("B", "BUY", 2.0),
                ("C", "WEAK BUY", 1.0),
                ("D", "WEAK SELL", -1.0),
                ("E", "SELL", -2.0),
                ("F", "STRONG SELL", -3.0),
            ]

            for symbol, signal_type, expected in test_cases:
                tracker.apply_signal(symbol, signal_type, today)
                assert tracker.sentiments[symbol].score == expected, \
                    f"{signal_type} should have spike of {expected}"

    def test_cumulative_signals(self):
        """Multiple signals should accumulate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            tracker.apply_signal("BTC", "BUY", today)  # +2
            tracker.apply_signal("BTC", "WEAK BUY", today)  # +1

            assert tracker.sentiments["BTC"].score == 3.0

    def test_opposing_signals_cancel(self):
        """Opposite signals should cancel out."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            tracker.apply_signal("BTC", "BUY", today)  # +2
            tracker.apply_signal("BTC", "SELL", today)  # -2

            assert tracker.sentiments["BTC"].score == 0.0

    def test_unknown_signal_type_ignored(self):
        """Unknown signal types should be ignored (no spike)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            spike = tracker.apply_signal("BTC", "HOLD", today)

            assert spike == 0.0
            assert "BTC" not in tracker.sentiments

    def test_token_name_stored(self):
        """Token name should be stored with sentiment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            tracker.apply_signal("BTC", "BUY", today, token_name="Bitcoin")

            assert tracker.sentiments["BTC"].token_name == "Bitcoin"


class TestRanking:
    """Tests for token ranking and candidate selection."""

    def test_ranked_tokens_sorted_descending(self):
        """Tokens should be sorted by score, highest first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            tracker.apply_signal("A", "STRONG BUY", today)  # +3
            tracker.apply_signal("B", "BUY", today)  # +2
            tracker.apply_signal("C", "WEAK BUY", today)  # +1
            tracker.apply_signal("D", "SELL", today)  # -2

            ranked = tracker.get_ranked_tokens()

            symbols = [s for s, _ in ranked]
            assert symbols == ["A", "B", "C", "D"]

    def test_long_candidates_positive_only(self):
        """Long candidates should only include positive sentiment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            tracker.apply_signal("A", "STRONG BUY", today)  # +3
            tracker.apply_signal("B", "BUY", today)  # +2
            tracker.apply_signal("C", "SELL", today)  # -2
            tracker.apply_signal("D", "STRONG SELL", today)  # -3

            longs = tracker.get_long_candidates(n=5)

            assert longs == ["A", "B"]
            assert "C" not in longs
            assert "D" not in longs

    def test_short_candidates_negative_only(self):
        """Short candidates should only include negative sentiment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            tracker.apply_signal("A", "STRONG BUY", today)  # +3
            tracker.apply_signal("B", "BUY", today)  # +2
            tracker.apply_signal("C", "SELL", today)  # -2
            tracker.apply_signal("D", "STRONG SELL", today)  # -3

            shorts = tracker.get_short_candidates(n=3)

            assert "A" not in shorts
            assert "B" not in shorts
            # Should include most negative
            assert "C" in shorts or "D" in shorts

    def test_long_candidates_limited_by_n(self):
        """Should return at most N long candidates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            for i, symbol in enumerate(["A", "B", "C", "D", "E", "F", "G"]):
                tracker.apply_signal(symbol, "BUY", today)

            longs = tracker.get_long_candidates(n=5)

            assert len(longs) == 5

    def test_fewer_candidates_than_n(self):
        """Should return all available if fewer than N."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            tracker.apply_signal("A", "BUY", today)
            tracker.apply_signal("B", "BUY", today)

            longs = tracker.get_long_candidates(n=5)

            assert len(longs) == 2
            assert "A" in longs
            assert "B" in longs


class TestPersistence:
    """Tests for state file persistence."""

    def test_save_and_load(self):
        """State should persist across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sentiment.json"
            today = date.today()

            # Create and save
            tracker1 = SentimentTracker(state_file)
            tracker1.apply_signal("BTC", "STRONG BUY", today)
            tracker1.apply_signal("ETH", "SELL", today)
            tracker1.last_processed_date = today.isoformat()
            tracker1.save()

            # Load in new instance
            tracker2 = SentimentTracker(state_file)

            assert tracker2.sentiments["BTC"].score == 3.0
            assert tracker2.sentiments["ETH"].score == -2.0
            assert tracker2.last_processed_date == today.isoformat()

    def test_load_empty_file(self):
        """Should handle non-existent file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "nonexistent.json"

            tracker = SentimentTracker(state_file)

            assert tracker.sentiments == {}
            assert tracker.last_processed_date is None

    def test_load_corrupted_file(self):
        """Should handle corrupted file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sentiment.json"

            # Write invalid JSON
            state_file.write_text("not valid json {{{")

            tracker = SentimentTracker(state_file)

            assert tracker.sentiments == {}


class TestProcessDay:
    """Tests for the process_day convenience method."""

    def test_process_day_applies_decay_then_signals(self):
        """Process day should apply decay before signals."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")

            day_0 = date(2025, 1, 1)
            day_hl = day_0 + timedelta(days=int(HALF_LIFE))

            # Initial signal
            tracker.apply_signal("BTC", "BUY", day_0)  # +2
            tracker.last_processed_date = day_0.isoformat()

            # Process one half-life later with new signal
            signals = [MockSignal("BTC", "WEAK BUY")]
            result = tracker.process_day(signals, day_hl)

            # Should be: 2.0 * 0.5 (decay) + 1.0 (new signal) = 2.0
            assert abs(tracker.sentiments["BTC"].score - 2.0) < 0.01

    def test_process_day_returns_summary(self):
        """Process day should return useful summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            signals = [
                MockSignal("BTC", "BUY"),
                MockSignal("ETH", "SELL"),
            ]
            result = tracker.process_day(signals, today)

            assert "date" in result
            assert "spikes_applied" in result
            assert "long_candidates" in result
            assert "short_candidates" in result


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_score_excluded_from_candidates(self):
        """Tokens with zero score should not be candidates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            tracker.apply_signal("BTC", "BUY", today)  # +2
            tracker.apply_signal("ETH", "SELL", today)  # -2
            # Canceled out:
            tracker.apply_signal("SOL", "BUY", today)
            tracker.apply_signal("SOL", "SELL", today)  # = 0

            longs = tracker.get_long_candidates()
            shorts = tracker.get_short_candidates()

            assert "SOL" not in longs
            assert "SOL" not in shorts

    def test_reset_clears_all_state(self):
        """Reset should clear all sentiment state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            tracker.apply_signal("BTC", "BUY", today)
            tracker.last_processed_date = today.isoformat()

            tracker.reset()

            assert tracker.sentiments == {}
            assert tracker.last_processed_date is None

    def test_get_sentiment_for_unknown_symbol(self):
        """get_sentiment should return None for unknown symbols."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")

            assert tracker.get_sentiment("UNKNOWN") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
