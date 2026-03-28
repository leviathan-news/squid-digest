"""
Integration tests for sentiment-based portfolio system.

Tests edge cases and full workflow scenarios:
1. No positive sentiment tokens (hold cash, no longs)
2. Fewer than 5 positive tokens (only long available)
3. No negative sentiment tokens (no shorts)
4. Token not in price feed (skip with warning)
5. All sentiment decays to ~0 (close positions, hold cash)
6. First run with no history (start empty, build over time)
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import date, timedelta
from dataclasses import dataclass

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.backtest.sentiment_state import SentimentTracker
from squid_digest.backtest.sentiment_portfolio import (
    SentimentPortfolio,
    format_sentiment_portfolio_results,
)


@dataclass
class MockSignal:
    """Mock signal for testing."""
    symbol: str
    signal_type: str
    token_name: str = ""


class TestEdgeCaseNoPositiveSentiment:
    """Test behavior when no tokens have positive sentiment."""

    def test_no_long_candidates_holds_cash(self):
        """When all sentiment is negative, portfolio should only short or hold cash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sentiment.json"
            portfolio_file = Path(tmpdir) / "portfolio.json"

            tracker = SentimentTracker(state_file)
            today = date.today()

            # Only negative signals
            tracker.apply_signal("DOGE", "SELL", today)
            tracker.apply_signal("SHIB", "STRONG SELL", today)
            tracker.apply_signal("PEPE", "WEAK SELL", today)

            long_candidates = tracker.get_long_candidates(n=5)
            short_candidates = tracker.get_short_candidates(n=3)

            assert len(long_candidates) == 0, "Should have no long candidates"
            assert len(short_candidates) == 3, "Should have 3 short candidates"

            # Portfolio should work with only shorts
            portfolio = SentimentPortfolio(cash=10000.0)
            prices = {"DOGE": 0.10, "SHIB": 0.00001, "PEPE": 0.000005}

            results = portfolio.rebalance(
                long_targets=[],
                short_targets=short_candidates,
                prices=prices,
                date=today,
            )

            # Should have shorts only
            assert len(results["long_positions"]) == 0
            assert len(results["short_positions"]) == 3

            # Total value should be maintained
            total = portfolio.get_total_value(prices)
            assert abs(total - 10000) < 100, "Total should be close to initial capital"


class TestEdgeCaseFewerThan5Positive:
    """Test behavior when fewer than 5 tokens have positive sentiment."""

    def test_only_available_tokens_used(self):
        """Should only long available positive tokens, not pad to 5."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            # Only 2 positive signals
            tracker.apply_signal("BTC", "BUY", today)
            tracker.apply_signal("ETH", "WEAK BUY", today)

            long_candidates = tracker.get_long_candidates(n=5)
            assert len(long_candidates) == 2, "Should have only 2 long candidates"
            assert "BTC" in long_candidates
            assert "ETH" in long_candidates

    def test_portfolio_handles_fewer_longs(self):
        """Portfolio should allocate correctly with fewer than 5 longs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            portfolio = SentimentPortfolio(cash=10000.0)
            prices = {"BTC": 50000.0, "ETH": 3000.0}
            today = date.today()

            results = portfolio.rebalance(
                long_targets=["BTC", "ETH"],
                short_targets=[],
                prices=prices,
                date=today,
            )

            # Should have 2 longs
            assert len(results["long_positions"]) == 2
            # 60% / 2 = 30% each
            btc_value = portfolio.get_position_value("BTC", prices)
            eth_value = portfolio.get_position_value("ETH", prices)
            assert abs(btc_value - eth_value) < 100, "Positions should be roughly equal"


class TestEdgeCaseNoNegativeSentiment:
    """Test behavior when no tokens have negative sentiment."""

    def test_no_short_candidates(self):
        """When all sentiment is positive, portfolio should only long."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            # Only positive signals
            tracker.apply_signal("BTC", "STRONG BUY", today)
            tracker.apply_signal("ETH", "BUY", today)
            tracker.apply_signal("SOL", "WEAK BUY", today)

            long_candidates = tracker.get_long_candidates(n=5)
            short_candidates = tracker.get_short_candidates(n=3)

            assert len(long_candidates) == 3
            assert len(short_candidates) == 0, "Should have no short candidates"

    def test_portfolio_handles_no_shorts(self):
        """Portfolio should work correctly with no short positions."""
        portfolio = SentimentPortfolio(cash=10000.0)
        prices = {"BTC": 50000.0, "ETH": 3000.0, "SOL": 100.0}
        today = date.today()

        results = portfolio.rebalance(
            long_targets=["BTC", "ETH", "SOL"],
            short_targets=[],
            prices=prices,
            date=today,
        )

        assert len(results["short_positions"]) == 0
        assert len(results["long_positions"]) == 3
        # Cash should have 40% (10% reserve + 30% unused short allocation)
        assert portfolio.cash > 3000, "Should have ~40% cash remaining"


class TestEdgeCaseTokenNotInPriceFeed:
    """Test behavior when a candidate token has no price available."""

    def test_missing_price_token_skipped(self):
        """Tokens without prices should be skipped, others should proceed."""
        portfolio = SentimentPortfolio(cash=10000.0)
        today = date.today()

        # BTC has price, FAKE does not
        prices = {"BTC": 50000.0}  # FAKE missing

        results = portfolio.rebalance(
            long_targets=["BTC", "FAKE"],  # FAKE will be filtered out
            short_targets=[],
            prices=prices,
            date=today,
        )

        # Only BTC should be in positions
        assert "BTC" in results["long_positions"]
        assert "FAKE" not in results["long_positions"]
        assert len(results["long_positions"]) == 1


class TestEdgeCaseAllSentimentDecayed:
    """Test behavior when all sentiment has decayed to near zero."""

    def test_long_decay_closes_positions(self):
        """After many days of decay, positions should be closed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")

            # Apply signal far enough in the past for score to zero out
            hl = SentimentTracker.HALF_LIFE_DAYS
            past_date = date.today() - timedelta(days=int(hl * 10))
            tracker.apply_signal("BTC", "WEAK BUY", past_date)  # +1.0

            # Apply decay to today
            tracker.apply_decay(date.today())

            # Score should be effectively zero
            assert tracker.sentiments["BTC"].score == 0.0, "Score should be zeroed"

            # Should have no candidates
            long_candidates = tracker.get_long_candidates()
            short_candidates = tracker.get_short_candidates()

            assert len(long_candidates) == 0
            assert len(short_candidates) == 0

    def test_portfolio_closes_all_on_no_targets(self):
        """Portfolio should close all positions when no targets remain."""
        portfolio = SentimentPortfolio(cash=5000.0)
        prices = {"BTC": 50000.0}
        today = date.today()

        # First rebalance - open position
        portfolio.rebalance(["BTC"], [], prices, today)
        assert "BTC" in portfolio.positions

        # Second rebalance - no targets, should close
        results = portfolio.rebalance([], [], prices, today + timedelta(days=1))

        assert len(portfolio.positions) == 0, "All positions should be closed"
        assert portfolio.cash > 4000, "Cash should be returned"


class TestEdgeCaseFirstRun:
    """Test behavior on first run with no history."""

    def test_fresh_start_empty_state(self):
        """Fresh sentiment tracker should start with empty state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "nonexistent.json"
            tracker = SentimentTracker(state_file)

            assert len(tracker.sentiments) == 0
            assert tracker.last_processed_date is None

    def test_fresh_portfolio_starts_with_cash(self):
        """Fresh portfolio should start with only cash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            portfolio_file = Path(tmpdir) / "nonexistent.json"
            portfolio = SentimentPortfolio.load(portfolio_file, initial_capital=10000.0)

            assert portfolio.cash == 10000.0
            assert len(portfolio.positions) == 0
            assert len(portfolio.trades) == 0

    def test_first_day_builds_positions(self):
        """First day with signals should build positions from scratch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sentiment.json"
            portfolio_file = Path(tmpdir) / "portfolio.json"

            # Fresh start
            tracker = SentimentTracker(state_file)
            today = date.today()

            # Apply first signals
            tracker.apply_signal("BTC", "STRONG BUY", today)
            tracker.apply_signal("ETH", "BUY", today)
            tracker.apply_signal("DOGE", "SELL", today)

            # Get candidates
            longs = tracker.get_long_candidates(n=5)
            shorts = tracker.get_short_candidates(n=3)

            assert longs == ["BTC", "ETH"]
            assert shorts == ["DOGE"]

            # Build portfolio
            portfolio = SentimentPortfolio.load(portfolio_file, initial_capital=10000.0)
            prices = {"BTC": 50000.0, "ETH": 3000.0, "DOGE": 0.10}

            results = portfolio.rebalance(longs, shorts, prices, today)

            # Should have positions
            assert len(results["long_positions"]) == 2
            assert len(results["short_positions"]) == 1
            assert len(results["trades_today"]) > 0


class TestFullWorkflowIntegration:
    """Test complete workflow from signals to formatted output."""

    def test_end_to_end_workflow(self):
        """Test complete workflow: signals -> sentiment -> portfolio -> format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "sentiment.json"
            portfolio_file = Path(tmpdir) / "portfolio.json"

            # Day 1: Fresh start
            tracker = SentimentTracker(state_file)
            day1 = date(2025, 1, 1)

            # Apply signals
            signals = [
                MockSignal("BTC", "STRONG BUY", "Bitcoin"),
                MockSignal("ETH", "BUY", "Ethereum"),
                MockSignal("DOGE", "SELL", "Dogecoin"),
            ]

            for signal in signals:
                tracker.apply_signal(
                    signal.symbol, signal.signal_type, day1, signal.token_name
                )

            # Get candidates
            longs = tracker.get_long_candidates(n=5)
            shorts = tracker.get_short_candidates(n=3)

            # Rebalance portfolio
            portfolio = SentimentPortfolio.load(portfolio_file, initial_capital=10000.0)
            prices = {"BTC": 50000.0, "ETH": 3000.0, "DOGE": 0.10}

            results = portfolio.rebalance(
                longs, shorts, prices, day1,
                token_names={s.symbol: s.token_name for s in signals}
            )

            # Save state
            tracker.save()
            portfolio.save(portfolio_file)

            # Verify state persists
            assert state_file.exists()
            assert portfolio_file.exists()

            # Format output (single strategy format)
            rankings = tracker.get_ranked_tokens()
            output = format_sentiment_portfolio_results(results, rankings, strategy_name="Momentum")

            # Verify output format
            assert "Momentum Strategy" in output
            assert "Portfolio Summary" in output
            assert "Current Positions" in output
            assert "BTC" in output
            assert "ETH" in output
            assert "DOGE" in output

            # Day 2: Continue with decay (one half-life later)
            hl = SentimentTracker.HALF_LIFE_DAYS
            day2 = day1 + timedelta(days=int(hl))

            tracker2 = SentimentTracker(state_file)
            tracker2.apply_decay(day2)

            # BTC should be around 1.5 (3 * 0.5)
            btc_score = tracker2.sentiments["BTC"].score
            assert 1.4 < btc_score < 1.6, f"BTC should be ~1.5 after decay, got {btc_score}"


class TestPriceIndependentOperations:
    """Test operations that don't require price fetching."""

    def test_sentiment_tracking_offline(self):
        """Sentiment tracking works without network access."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = SentimentTracker(Path(tmpdir) / "sentiment.json")
            today = date.today()

            # Apply many signals
            for i, symbol in enumerate(["A", "B", "C", "D", "E", "F", "G", "H"]):
                signal_type = "BUY" if i < 4 else "SELL"
                tracker.apply_signal(symbol, signal_type, today)

            # Rankings work
            ranked = tracker.get_ranked_tokens()
            assert len(ranked) == 8

            # Candidates work
            longs = tracker.get_long_candidates(n=3)
            shorts = tracker.get_short_candidates(n=2)

            assert len(longs) == 3
            assert len(shorts) == 2

            # Persistence works
            tracker.save()
            tracker2 = SentimentTracker(Path(tmpdir) / "sentiment.json")
            assert len(tracker2.sentiments) == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
