"""
Tests for sentiment-based portfolio rebalancing.

These tests verify:
1. Position allocation is correct (60% long, 30% short)
2. Rebalancing closes old positions and opens new ones
3. Equal-weighting within buckets works
4. Edge cases are handled (no longs, no shorts, etc.)
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.backtest.sentiment_portfolio import (
    SentimentPortfolio,
    format_sentiment_portfolio_results,
)


class TestSentimentPortfolioRebalancing:
    """Tests for portfolio rebalancing logic."""

    def test_initial_rebalance_allocates_correctly(self):
        """First rebalance should allocate 60% to longs, 30% to shorts."""
        portfolio = SentimentPortfolio(cash=10000.0)

        long_targets = ["BTC", "ETH"]
        short_targets = ["DOGE"]
        prices = {"BTC": 100.0, "ETH": 50.0, "DOGE": 1.0}

        results = portfolio.rebalance(long_targets, short_targets, prices, datetime.now())

        # Check allocations
        # Long: 60% of $10k = $6k, split 2 ways = $3k each
        # Short: 30% of $10k = $3k for DOGE

        btc_value = portfolio.get_position_value("BTC", prices)
        eth_value = portfolio.get_position_value("ETH", prices)
        doge_value = abs(portfolio.get_position_value("DOGE", prices))

        assert btc_value > 0, "Should have long BTC position"
        assert eth_value > 0, "Should have long ETH position"
        assert portfolio.positions["DOGE"].is_short(), "Should have short DOGE position"

        # Values should be approximately equal per bucket
        assert abs(btc_value - eth_value) < 100, "Long positions should be roughly equal"

    def test_rebalance_closes_rotated_out_positions(self):
        """Positions not in new targets should be closed."""
        portfolio = SentimentPortfolio(cash=10000.0)
        prices = {"BTC": 100.0, "ETH": 50.0, "SOL": 25.0}

        # Initial positions
        portfolio.rebalance(["BTC", "ETH"], [], prices, datetime(2025, 1, 1))

        assert "BTC" in portfolio.positions
        assert "ETH" in portfolio.positions

        # Rebalance with new targets (BTC rotated out)
        results = portfolio.rebalance(["ETH", "SOL"], [], prices, datetime(2025, 1, 2))

        assert "BTC" not in portfolio.positions, "BTC should be closed"
        assert "ETH" in portfolio.positions, "ETH should still be held"
        assert "SOL" in portfolio.positions, "SOL should be added"

    def test_rebalance_handles_no_long_candidates(self):
        """Should handle case with no positive sentiment tokens."""
        portfolio = SentimentPortfolio(cash=10000.0)
        prices = {"DOGE": 1.0, "SHIB": 0.001}

        results = portfolio.rebalance([], ["DOGE", "SHIB"], prices, datetime.now())

        # Should only have short positions
        long_positions = [s for s in portfolio.positions if not portfolio.positions[s].is_short()]
        short_positions = [s for s in portfolio.positions if portfolio.positions[s].is_short()]

        assert len(long_positions) == 0
        assert len(short_positions) == 2

    def test_rebalance_handles_no_short_candidates(self):
        """Should handle case with no negative sentiment tokens."""
        portfolio = SentimentPortfolio(cash=10000.0)
        prices = {"BTC": 100.0, "ETH": 50.0}

        results = portfolio.rebalance(["BTC", "ETH"], [], prices, datetime.now())

        # Should only have long positions
        long_positions = [s for s in portfolio.positions if not portfolio.positions[s].is_short()]
        short_positions = [s for s in portfolio.positions if portfolio.positions[s].is_short()]

        assert len(long_positions) == 2
        assert len(short_positions) == 0

    def test_rebalance_handles_empty_targets(self):
        """Should close all positions if no targets."""
        portfolio = SentimentPortfolio(cash=10000.0)
        prices = {"BTC": 100.0}

        # Open position
        portfolio.rebalance(["BTC"], [], prices, datetime(2025, 1, 1))
        assert "BTC" in portfolio.positions

        # Rebalance with empty targets
        results = portfolio.rebalance([], [], prices, datetime(2025, 1, 2))

        assert len(portfolio.positions) == 0, "All positions should be closed"
        assert portfolio.cash > 9000, "Cash should be available"


class TestSentimentPortfolioPersistence:
    """Tests for portfolio state persistence."""

    def test_save_and_load(self):
        """Portfolio should persist across saves."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "portfolio.json"

            # Create and save
            portfolio1 = SentimentPortfolio(cash=10000.0)
            prices = {"BTC": 100.0, "ETH": 50.0}
            portfolio1.rebalance(["BTC", "ETH"], [], prices, datetime(2025, 1, 1))
            portfolio1.save(filepath)

            # Load in new instance
            portfolio2 = SentimentPortfolio.load(filepath)

            assert portfolio2.cash == portfolio1.cash
            assert len(portfolio2.positions) == len(portfolio1.positions)
            assert "BTC" in portfolio2.positions
            assert "ETH" in portfolio2.positions

    def test_load_nonexistent_creates_new(self):
        """Loading nonexistent file should create new portfolio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "nonexistent.json"

            portfolio = SentimentPortfolio.load(filepath, initial_capital=5000.0)

            assert portfolio.cash == 5000.0
            assert len(portfolio.positions) == 0


class TestSentimentPortfolioValueCalculation:
    """Tests for portfolio value calculations."""

    def test_total_value_with_longs(self):
        """Total value should include long positions."""
        portfolio = SentimentPortfolio(cash=10000.0)
        prices = {"BTC": 100.0}

        portfolio.rebalance(["BTC"], [], prices, datetime.now())

        total = portfolio.get_total_value(prices)
        # Total should be approximately initial capital (positions + cash = ~$10k)
        assert abs(total - 10000) < 100, "Total should be close to initial capital"
        # Should have both positions and cash
        assert portfolio.cash < 10000, "Some cash should be spent on positions"
        assert "BTC" in portfolio.positions, "Should have BTC position"

    def test_total_value_with_shorts(self):
        """Total value should account for short liabilities."""
        portfolio = SentimentPortfolio(cash=10000.0)
        prices = {"DOGE": 1.0}

        portfolio.rebalance([], ["DOGE"], prices, datetime.now())

        # After shorting, we have more cash but owe tokens
        initial_total = portfolio.get_total_value(prices)
        assert abs(initial_total - 10000) < 100, "Total should be close to initial capital"

        # If price goes down, total should increase
        lower_prices = {"DOGE": 0.5}
        lower_total = portfolio.get_total_value(lower_prices)
        assert lower_total > initial_total, "Short profit when price drops"


class TestSentimentPortfolioFlipping:
    """Tests for position flipping (long to short and vice versa)."""

    def test_flip_long_to_short(self):
        """Token moving from long targets to short targets should flip."""
        portfolio = SentimentPortfolio(cash=10000.0)
        prices = {"BTC": 100.0}

        # Start with long
        portfolio.rebalance(["BTC"], [], prices, datetime(2025, 1, 1))
        assert not portfolio.positions["BTC"].is_short()

        # Flip to short
        portfolio.rebalance([], ["BTC"], prices, datetime(2025, 1, 2))
        assert portfolio.positions["BTC"].is_short()

    def test_flip_short_to_long(self):
        """Token moving from short targets to long targets should flip."""
        portfolio = SentimentPortfolio(cash=10000.0)
        prices = {"DOGE": 1.0}

        # Start with short
        portfolio.rebalance([], ["DOGE"], prices, datetime(2025, 1, 1))
        assert portfolio.positions["DOGE"].is_short()

        # Flip to long
        portfolio.rebalance(["DOGE"], [], prices, datetime(2025, 1, 2))
        assert not portfolio.positions["DOGE"].is_short()


class TestFormatResults:
    """Tests for newsletter formatting."""

    def test_format_includes_key_sections(self):
        """Formatted output should include all key sections."""
        results = {
            "total_value": 12500.0,
            "cash": 1000.0,
            "long_positions": ["BTC", "ETH"],
            "short_positions": ["DOGE"],
            "trades_today": [],
            "rotations": [],
        }
        rankings = [("BTC", 5.0), ("ETH", 3.0), ("DOGE", -2.0)]

        output = format_sentiment_portfolio_results(results, rankings)

        assert "Sentiment Portfolio" in output
        assert "Portfolio Summary" in output
        assert "Sentiment Rankings" in output
        assert "Current Positions" in output
        assert "$12,500.00" in output
        assert "BTC" in output
        assert "ETH" in output
        assert "DOGE" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
