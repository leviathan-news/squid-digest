"""
Sentiment-based portfolio that rebalances based on sentiment rankings.

Unlike the signal-driven Portfolio class, this portfolio:
- Holds positions based on sentiment rankings (not individual signals)
- Rebalances daily to top N positive (long) and bottom M negative (short)
- Equal-weights positions within long/short buckets
- Automatically rotates out positions when sentiment decays
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path

from .portfolio import Position, Trade


@dataclass
class SentimentPortfolio:
    """
    Portfolio that rebalances based on sentiment rankings.

    Allocation:
    - 60% to long positions (equally weighted)
    - 30% to short positions (equally weighted)
    - 10% cash reserve
    """

    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    daily_values: List[Tuple[str, float]] = field(default_factory=list)

    # Allocation percentages
    LONG_ALLOCATION = 0.60   # 60% to longs
    SHORT_ALLOCATION = 0.30  # 30% to shorts
    CASH_RESERVE = 0.10      # 10% cash buffer

    # Rebalancing threshold - only adjust if >10% off target
    REBALANCE_THRESHOLD = 0.10

    # Minimum trade size
    MIN_TRADE_VALUE = 1.0

    def get_position_value(self, symbol: str, prices: Dict[str, float]) -> float:
        """Get current value of a position."""
        if symbol not in self.positions:
            return 0.0

        position = self.positions[symbol]
        price = prices.get(symbol, position.entry_price)

        if position.is_short():
            # Short: liability (negative value)
            return -abs(position.quantity) * price
        else:
            return position.quantity * price

    def get_total_value(self, prices: Dict[str, float]) -> float:
        """Get total portfolio value including cash and positions."""
        total = self.cash

        for symbol, position in self.positions.items():
            price = prices.get(symbol, position.entry_price)

            if position.is_short():
                # Short: we received cash at entry, now owe tokens at current price
                # P&L = entry_value - current_value
                entry_value = abs(position.quantity) * position.entry_price
                current_value = abs(position.quantity) * price
                # Cash from short sale is in self.cash, liability is current_value
                total -= current_value
            else:
                total += position.quantity * price

        return total

    def close_position(
        self,
        symbol: str,
        price: float,
        date: datetime,
        reason: str = "REBALANCE",
    ) -> Optional[Trade]:
        """Close an existing position."""
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        if position.is_short():
            # Cover short
            quantity = abs(position.quantity)
            cover_cost = quantity * price
            entry_value = quantity * position.entry_price
            pnl = entry_value - cover_cost  # Profit if price went down

            self.cash -= cover_cost

            trade = Trade(
                date=date,
                symbol=symbol,
                token_name=position.token_name,
                action='COVER',
                quantity=quantity,
                price=price,
                value=cover_cost,
                signal_type=reason,
                pnl=pnl,
                entry_price=position.entry_price,
            )
        else:
            # Sell long
            quantity = position.quantity
            sell_value = quantity * price
            pnl = sell_value - (quantity * position.entry_price)

            self.cash += sell_value

            trade = Trade(
                date=date,
                symbol=symbol,
                token_name=position.token_name,
                action='SELL',
                quantity=quantity,
                price=price,
                value=sell_value,
                signal_type=reason,
                pnl=pnl,
                entry_price=position.entry_price,
            )

        del self.positions[symbol]
        self.trades.append(trade)
        return trade

    def open_long(
        self,
        symbol: str,
        token_name: str,
        target_value: float,
        price: float,
        date: datetime,
    ) -> Optional[Trade]:
        """Open or adjust a long position to target value."""
        if target_value < self.MIN_TRADE_VALUE:
            return None

        if symbol in self.positions:
            position = self.positions[symbol]
            if position.is_short():
                # Need to close short first
                self.close_position(symbol, price, date, "SENTIMENT_FLIP")

        current_value = self.get_position_value(symbol, {symbol: price})
        diff = target_value - current_value

        # Check if rebalance is needed
        if current_value > 0 and abs(diff) / target_value < self.REBALANCE_THRESHOLD:
            return None  # Already close enough

        if diff <= 0:
            return None  # Already at or above target

        # Buy to target
        buy_value = min(diff, self.cash)
        if buy_value < self.MIN_TRADE_VALUE:
            return None

        quantity = buy_value / price
        self.cash -= buy_value

        if symbol in self.positions:
            # Add to existing position
            existing = self.positions[symbol]
            total_quantity = existing.quantity + quantity
            total_cost = (existing.quantity * existing.entry_price) + buy_value
            avg_price = total_cost / total_quantity

            self.positions[symbol] = Position(
                symbol=symbol,
                token_name=token_name,
                quantity=total_quantity,
                entry_price=avg_price,
                entry_date=existing.entry_date,
                entry_signal="SENTIMENT_LONG",
            )
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                token_name=token_name,
                quantity=quantity,
                entry_price=price,
                entry_date=date,
                entry_signal="SENTIMENT_LONG",
            )

        trade = Trade(
            date=date,
            symbol=symbol,
            token_name=token_name,
            action='BUY',
            quantity=quantity,
            price=price,
            value=buy_value,
            signal_type="SENTIMENT_LONG",
        )

        self.trades.append(trade)
        return trade

    def open_short(
        self,
        symbol: str,
        token_name: str,
        target_value: float,
        price: float,
        date: datetime,
    ) -> Optional[Trade]:
        """Open or adjust a short position to target value."""
        if target_value < self.MIN_TRADE_VALUE:
            return None

        if symbol in self.positions:
            position = self.positions[symbol]
            if not position.is_short():
                # Need to close long first
                self.close_position(symbol, price, date, "SENTIMENT_FLIP")

        # For shorts, we track liability (positive target_value means short position)
        current_liability = 0.0
        if symbol in self.positions and self.positions[symbol].is_short():
            current_liability = abs(self.positions[symbol].quantity) * price

        diff = target_value - current_liability

        if current_liability > 0 and abs(diff) / target_value < self.REBALANCE_THRESHOLD:
            return None  # Already close enough

        if diff <= 0:
            return None  # Already at or above target

        # Short to target
        short_value = diff
        quantity = short_value / price

        # Add cash from short sale
        self.cash += short_value

        if symbol in self.positions and self.positions[symbol].is_short():
            # Add to existing short
            existing = self.positions[symbol]
            total_quantity = abs(existing.quantity) + quantity
            total_entry = (abs(existing.quantity) * existing.entry_price) + short_value
            avg_price = total_entry / total_quantity

            self.positions[symbol] = Position(
                symbol=symbol,
                token_name=existing.token_name,
                quantity=-total_quantity,  # Negative for short
                entry_price=avg_price,
                entry_date=existing.entry_date,
                entry_signal="SENTIMENT_SHORT",
            )
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                token_name=token_name,
                quantity=-quantity,  # Negative for short
                entry_price=price,
                entry_date=date,
                entry_signal="SENTIMENT_SHORT",
            )

        trade = Trade(
            date=date,
            symbol=symbol,
            token_name=token_name,
            action='SHORT',
            quantity=quantity,
            price=price,
            value=short_value,
            signal_type="SENTIMENT_SHORT",
        )

        self.trades.append(trade)
        return trade

    def rebalance(
        self,
        long_targets: List[str],
        short_targets: List[str],
        prices: Dict[str, float],
        date: datetime,
        token_names: Optional[Dict[str, str]] = None,
        sentiments: Optional[Dict[str, float]] = None,
    ) -> Dict:
        """
        Rebalance portfolio to match target positions.

        1. Close positions no longer in targets
        2. Open new positions for new targets
        3. Weight by sentiment score magnitude (falls back to equal-weight)

        Args:
            sentiments: Optional dict of {symbol: score} for weighted allocation.
                        Only actionable (priceable) targets are weighted.

        Returns summary of changes made.
        """
        if token_names is None:
            token_names = {}

        all_targets = set(long_targets) | set(short_targets)
        trades_today = []
        rotations = []

        # 1. Close positions not in targets
        for symbol in list(self.positions.keys()):
            if symbol not in all_targets:
                if symbol in prices:
                    trade = self.close_position(symbol, prices[symbol], date, "ROTATION")
                    if trade:
                        trades_today.append(trade)
                        rotations.append(f"Closed {symbol} (no longer in targets)")

        # 2. Calculate target allocations
        total_value = self.get_total_value(prices)

        long_total = total_value * self.LONG_ALLOCATION
        short_total = total_value * self.SHORT_ALLOCATION

        # Compute per-position allocations — weighted by sentiment if available,
        # normalized over actionable targets only (those with prices).
        actionable_longs = [s for s in long_targets if s in prices]
        actionable_shorts = [s for s in short_targets if s in prices]

        if sentiments and actionable_longs:
            long_scores = {s: max(abs(sentiments.get(s, 1.0)), 0.1) for s in actionable_longs}
            total_long_score = sum(long_scores.values())
            if total_long_score >= 0.01:
                long_allocations = {s: long_total * (score / total_long_score) for s, score in long_scores.items()}
            else:
                long_allocations = {s: long_total / len(actionable_longs) for s in actionable_longs}
        elif actionable_longs:
            long_allocations = {s: long_total / len(actionable_longs) for s in actionable_longs}
        else:
            long_allocations = {}

        if sentiments and actionable_shorts:
            short_scores = {s: max(abs(sentiments.get(s, 1.0)), 0.1) for s in actionable_shorts}
            total_short_score = sum(short_scores.values())
            if total_short_score >= 0.01:
                short_allocations = {s: short_total * (score / total_short_score) for s, score in short_scores.items()}
            else:
                short_allocations = {s: short_total / len(actionable_shorts) for s in actionable_shorts}
        elif actionable_shorts:
            short_allocations = {s: short_total / len(actionable_shorts) for s in actionable_shorts}
        else:
            short_allocations = {}

        # 3. Open/adjust long positions
        for symbol in long_targets:
            if symbol not in prices:
                continue
            token_name = token_names.get(symbol, symbol)
            target_value = long_allocations.get(symbol, 0)
            trade = self.open_long(symbol, token_name, target_value, prices[symbol], date)
            if trade:
                trades_today.append(trade)

        # 4. Open/adjust short positions
        for symbol in short_targets:
            if symbol not in prices:
                continue
            token_name = token_names.get(symbol, symbol)
            target_value = short_allocations.get(symbol, 0)
            trade = self.open_short(symbol, token_name, target_value, prices[symbol], date)
            if trade:
                trades_today.append(trade)

        # Record daily value
        final_value = self.get_total_value(prices)
        self.daily_values.append((date.isoformat(), final_value))

        return {
            "date": date.isoformat(),
            "trades_today": trades_today,
            "rotations": rotations,
            "total_value": final_value,
            "long_positions": [s for s in self.positions if not self.positions[s].is_short()],
            "short_positions": [s for s in self.positions if self.positions[s].is_short()],
            "cash": self.cash,
        }

    def to_dict(self) -> dict:
        """Convert portfolio to dict for persistence."""
        return {
            "cash": self.cash,
            "positions": {
                symbol: {
                    "symbol": pos.symbol,
                    "token_name": pos.token_name,
                    "quantity": pos.quantity,
                    "entry_price": pos.entry_price,
                    "entry_date": pos.entry_date.isoformat(),
                    "entry_signal": pos.entry_signal,
                }
                for symbol, pos in self.positions.items()
            },
            "trades": [
                {
                    "date": t.date.isoformat(),
                    "symbol": t.symbol,
                    "token_name": t.token_name,
                    "action": t.action,
                    "quantity": t.quantity,
                    "price": t.price,
                    "value": t.value,
                    "signal_type": t.signal_type,
                    "pnl": t.pnl,
                    "entry_price": t.entry_price,
                }
                for t in self.trades
            ],
            "daily_values": self.daily_values,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SentimentPortfolio":
        """Create portfolio from dict."""
        positions = {}
        for symbol, pos_data in data.get("positions", {}).items():
            positions[symbol] = Position(
                symbol=pos_data["symbol"],
                token_name=pos_data["token_name"],
                quantity=pos_data["quantity"],
                entry_price=pos_data["entry_price"],
                entry_date=datetime.fromisoformat(pos_data["entry_date"]),
                entry_signal=pos_data["entry_signal"],
            )

        trades = []
        for t_data in data.get("trades", []):
            trades.append(Trade(
                date=datetime.fromisoformat(t_data["date"]),
                symbol=t_data["symbol"],
                token_name=t_data["token_name"],
                action=t_data["action"],
                quantity=t_data["quantity"],
                price=t_data["price"],
                value=t_data["value"],
                signal_type=t_data["signal_type"],
                pnl=t_data.get("pnl"),
                entry_price=t_data.get("entry_price"),
            ))

        return cls(
            cash=data.get("cash", 10000.0),
            positions=positions,
            trades=trades,
            daily_values=data.get("daily_values", []),
        )

    def save(self, filepath: Path) -> None:
        """Save portfolio state to file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: Path, initial_capital: float = 10000.0) -> "SentimentPortfolio":
        """Load portfolio from file, or create new if not found."""
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                return cls.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load portfolio: {e}")

        return cls(cash=initial_capital)


def format_sentiment_portfolio_results(
    results: Dict,
    sentiment_rankings: List[Tuple[str, float]],
    initial_capital: float = 10000.0,
    strategy_name: str = "Momentum",
) -> str:
    """
    Format sentiment portfolio results for newsletter.

    Returns markdown string.
    """
    lines = [f"### {strategy_name} Strategy\n"]

    # Portfolio summary
    total_value = results.get("total_value", 0)
    total_return = ((total_value - initial_capital) / initial_capital) * 100
    cash = results.get("cash", 0)

    lines.append("### Portfolio Summary\n")
    lines.append(f"- **Portfolio Value:** `${total_value:,.2f}`")
    lines.append(f"- **Total Return:** `{total_return:+.2f}%`")
    lines.append(f"- **Cash:** `${cash:,.2f}`\n")

    # Current positions
    long_positions = results.get("long_positions", [])
    short_positions = results.get("short_positions", [])

    lines.append("### Current Positions\n")
    if long_positions:
        lines.append(f"**Long ({len(long_positions)}):** {', '.join(long_positions)}")
    else:
        lines.append("**Long:** None")

    if short_positions:
        lines.append(f"**Short ({len(short_positions)}):** {', '.join(short_positions)}")
    else:
        lines.append("**Short:** None")

    lines.append("")

    # Today's trades
    trades = results.get("trades_today", [])
    if trades:
        lines.append("### Today's Trades\n")
        for trade in trades:
            emoji = "🟢" if trade.action in ('BUY',) else "🔴" if trade.action in ('SELL', 'SHORT') else "🟡"
            lines.append(f"- {emoji} {trade.action} {trade.quantity:.4f} {trade.symbol} @ ${trade.price:.2f}")
        lines.append("")

    # Rotations
    rotations = results.get("rotations", [])
    if rotations:
        lines.append("### Rotations\n")
        for rotation in rotations:
            lines.append(f"- {rotation}")
        lines.append("")

    return "\n".join(lines)


# BTC price at portfolio inception (Jan 1, 2026) — used for benchmark comparison.
# Source: CoinGecko historical price for 2026-01-01.
BTC_INCEPTION_PRICE = 93400.0


def format_dual_sentiment_portfolios(
    momentum_results: Dict,
    contrarian_results: Dict,
    sentiment_rankings: List[Tuple[str, float]],
    initial_capital: float = 10000.0,
    btc_price: Optional[float] = None,
) -> str:
    """
    Format both momentum and contrarian portfolio results for newsletter.

    Includes sentiment rankings header and both strategy summaries.

    Args:
        btc_price: Current BTC price for benchmark comparison (optional).

    Returns markdown string.
    """
    lines = ["## 📈 Sentiment Portfolio\n"]

    # How It Works explanation
    lines.append("*Daily signals accumulate into sentiment scores (14-day half-life decay). "
                 "Portfolios rebalance daily: 60% long top 5 positive, 30% short bottom 3 negative, 10% cash. "
                 "Momentum follows sentiment; Contrarian inverts it.*\n")

    # Sentiment Rankings — compact list format (renders well in Telegram + email)
    lines.append("### Current Sentiment Rankings\n")

    # Top 5 positive (momentum long, contrarian short)
    long_parts = []
    for symbol, score in sentiment_rankings:
        if score > 0 and len(long_parts) < 5:
            long_parts.append(f"{symbol} (+{score:.2f})")

    # Bottom 3 negative (momentum short, contrarian long)
    negative_tokens = [(s, score) for s, score in sentiment_rankings if score < 0]
    short_parts = [f"{s} ({score:.2f})" for s, score in negative_tokens[-3:]]

    if long_parts:
        lines.append(f"🟢 **Long:** {' · '.join(long_parts)}")
    if short_parts:
        lines.append(f"🔴 **Short:** {' · '.join(short_parts)}")

    lines.append("")

    # BTC benchmark comparison
    if btc_price and BTC_INCEPTION_PRICE > 0:
        btc_return = ((btc_price / BTC_INCEPTION_PRICE) - 1) * 100
        momentum_return = ((momentum_results.get("total_value", initial_capital) / initial_capital) - 1) * 100
        contrarian_return = ((contrarian_results.get("total_value", initial_capital) / initial_capital) - 1) * 100
        lines.append("### Benchmark\n")
        lines.append(f"- **BTC Buy & Hold:** `{btc_return:+.2f}%`")
        lines.append(f"- **Momentum Alpha vs BTC:** `{momentum_return - btc_return:+.2f}%`")
        lines.append(f"- **Contrarian Alpha vs BTC:** `{contrarian_return - btc_return:+.2f}%`")
        lines.append("")

    # Momentum Strategy
    lines.append(format_sentiment_portfolio_results(
        momentum_results, sentiment_rankings, initial_capital, "Momentum"
    ))

    # Contrarian Strategy
    lines.append(format_sentiment_portfolio_results(
        contrarian_results, sentiment_rankings, initial_capital, "Contrarian"
    ))

    return "\n".join(lines)
