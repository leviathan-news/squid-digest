"""
Sentiment state tracking for portfolio construction.

Each token has a sentiment score that:
- Starts at 0
- Spikes up/down based on news signals (weighted by strength)
- Decays with a 7-day half-life back toward 0

The portfolio is constructed by:
- Going LONG on top 5 positive sentiment tokens
- Going SHORT on bottom 3 negative sentiment tokens
"""

import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class TokenSentiment:
    """Sentiment state for a single token."""
    symbol: str
    score: float  # Current sentiment score (can be positive or negative)
    last_signal_date: str  # ISO format date of last signal applied
    token_name: Optional[str] = None  # Human-readable name

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": self.score,
            "last_signal_date": self.last_signal_date,
            "token_name": self.token_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TokenSentiment":
        return cls(
            symbol=data["symbol"],
            score=data["score"],
            last_signal_date=data["last_signal_date"],
            token_name=data.get("token_name"),
        )


class SentimentTracker:
    """
    Tracks sentiment scores for all tokens with decay over time.

    Sentiment decays with a 7-day half-life (score drops by 50% every 7 days).
    Signals add/subtract from the score based on strength.
    """

    HALF_LIFE_DAYS = 7.0

    # Spike weights for each signal type
    SPIKE_WEIGHTS = {
        'STRONG BUY': +3.0,
        'BUY': +2.0,
        'WEAK BUY': +1.0,
        'WEAK SELL': -1.0,
        'SELL': -2.0,
        'STRONG SELL': -3.0,
    }

    def __init__(self, state_file: Path):
        """Initialize tracker with path to state file."""
        self.state_file = Path(state_file)
        self.sentiments: Dict[str, TokenSentiment] = {}
        self.last_processed_date: Optional[str] = None
        self._load()

    def _load(self) -> None:
        """Load state from file if it exists."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                self.last_processed_date = data.get("last_processed_date")
                for symbol, sent_data in data.get("sentiments", {}).items():
                    self.sentiments[symbol] = TokenSentiment.from_dict(sent_data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load sentiment state: {e}")
                self.sentiments = {}
                self.last_processed_date = None

    def save(self) -> None:
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_processed_date": self.last_processed_date,
            "sentiments": {
                symbol: sent.to_dict()
                for symbol, sent in self.sentiments.items()
            }
        }
        with open(self.state_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _calculate_decay_factor(self, days_elapsed: float) -> float:
        """
        Calculate decay factor for given number of days.

        Uses exponential decay with 7-day half-life:
        factor = 0.5 ^ (days / 7)

        Examples:
        - 0 days: factor = 1.0 (no decay)
        - 7 days: factor = 0.5 (half)
        - 14 days: factor = 0.25 (quarter)
        """
        if days_elapsed <= 0:
            return 1.0
        return math.pow(0.5, days_elapsed / self.HALF_LIFE_DAYS)

    def _parse_date(self, date_str: str) -> date:
        """Parse ISO format date string to date object."""
        if 'T' in date_str:
            return datetime.fromisoformat(date_str).date()
        return datetime.strptime(date_str, '%Y-%m-%d').date()

    def apply_decay(self, as_of_date: date) -> Dict[str, float]:
        """
        Apply time-based decay to all sentiment scores.

        Decay is calculated from each token's last_signal_date to as_of_date.
        Returns dict of {symbol: decay_applied} for logging.
        """
        decay_applied = {}

        for symbol, sentiment in self.sentiments.items():
            if sentiment.score == 0:
                continue

            last_date = self._parse_date(sentiment.last_signal_date)
            days_elapsed = (as_of_date - last_date).days

            if days_elapsed > 0:
                decay_factor = self._calculate_decay_factor(days_elapsed)
                old_score = sentiment.score
                sentiment.score = old_score * decay_factor

                # Zero out very small scores to avoid floating point noise
                if abs(sentiment.score) < 0.01:
                    sentiment.score = 0.0

                decay_applied[symbol] = old_score - sentiment.score

        return decay_applied

    def apply_signal(
        self,
        symbol: str,
        signal_type: str,
        signal_date: date,
        token_name: Optional[str] = None,
    ) -> float:
        """
        Apply a signal to update token sentiment.

        Returns the spike amount applied.
        """
        spike = self.SPIKE_WEIGHTS.get(signal_type, 0.0)
        if spike == 0:
            return 0.0

        date_str = signal_date.isoformat()

        if symbol not in self.sentiments:
            self.sentiments[symbol] = TokenSentiment(
                symbol=symbol,
                score=0.0,
                last_signal_date=date_str,
                token_name=token_name,
            )

        self.sentiments[symbol].score += spike
        self.sentiments[symbol].last_signal_date = date_str
        if token_name:
            self.sentiments[symbol].token_name = token_name

        return spike

    def get_ranked_tokens(self) -> List[Tuple[str, float]]:
        """
        Return all tokens sorted by sentiment score (highest first).

        Returns list of (symbol, score) tuples.
        """
        return sorted(
            [(s, sent.score) for s, sent in self.sentiments.items()],
            key=lambda x: -x[1]
        )

    def get_long_candidates(self, n: int = 5) -> List[str]:
        """
        Get top N tokens with positive sentiment for long positions.

        Returns list of symbols.
        """
        ranked = self.get_ranked_tokens()
        return [symbol for symbol, score in ranked if score > 0][:n]

    def get_short_candidates(self, n: int = 3) -> List[str]:
        """
        Get bottom N tokens with negative sentiment for short positions.

        Returns list of symbols (most negative first in the result,
        but these are the N most negative overall).
        """
        ranked = self.get_ranked_tokens()
        # Get tokens with negative scores, take the N most negative
        negative = [(s, score) for s, score in ranked if score < 0]
        # Most negative are at the end of ranked list, so we take last N
        return [symbol for symbol, score in negative[-n:]]

    def get_sentiment(self, symbol: str) -> Optional[float]:
        """Get current sentiment score for a symbol."""
        if symbol in self.sentiments:
            return self.sentiments[symbol].score
        return None

    def get_all_sentiments(self) -> Dict[str, float]:
        """Get dict of all sentiment scores."""
        return {s: sent.score for s, sent in self.sentiments.items()}

    def process_day(
        self,
        signals: List,  # List of Signal objects
        signal_date: date,
    ) -> dict:
        """
        Process a full day's worth of signals.

        1. Apply decay from last processed date to signal_date
        2. Apply all signals for the day
        3. Update last_processed_date

        Returns summary dict with decay and spike info.
        """
        # Apply decay first
        decay_applied = self.apply_decay(signal_date)

        # Apply signals
        spikes_applied = {}
        for signal in signals:
            spike = self.apply_signal(
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                signal_date=signal_date,
                token_name=getattr(signal, 'token_name', None),
            )
            if spike != 0:
                spikes_applied[signal.symbol] = spike

        # Update last processed date
        self.last_processed_date = signal_date.isoformat()

        return {
            "date": signal_date.isoformat(),
            "decay_applied": decay_applied,
            "spikes_applied": spikes_applied,
            "long_candidates": self.get_long_candidates(),
            "short_candidates": self.get_short_candidates(),
        }

    def reset(self) -> None:
        """Clear all sentiment state (for testing or reinitialization)."""
        self.sentiments = {}
        self.last_processed_date = None
