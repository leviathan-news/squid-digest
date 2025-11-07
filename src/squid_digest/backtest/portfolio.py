"""Portfolio simulation for backtesting trading signals."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .signal_parser import Signal


@dataclass
class Position:
    """Represents a position in a token."""
    symbol: str
    token_name: str
    quantity: float
    entry_price: float
    entry_date: datetime
    entry_signal: str  # Signal type that triggered entry


@dataclass
class Trade:
    """Represents a completed trade."""
    date: datetime
    symbol: str
    token_name: str
    action: str  # 'BUY' or 'SELL'
    quantity: float
    price: float
    value: float  # quantity * price
    signal_type: str
    pnl: Optional[float] = None  # For sells, the profit/loss
    entry_price: Optional[float] = None  # For sells, the original entry price


@dataclass
class Portfolio:
    """Portfolio state for backtesting."""
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    daily_values: List[tuple] = field(default_factory=list)  # (date, total_value)
    
    # Signal strength multipliers
    SIGNAL_WEIGHTS = {
        'STRONG BUY': 2.0,
        'BUY': 1.0,
        'WEAK BUY': 0.5,
        'WEAK SELL': -0.5,
        'SELL': -1.0,
        'STRONG SELL': -2.0,
    }
    
    def get_position_value(self, symbol: str, price: float) -> float:
        """Get current value of a position."""
        if symbol not in self.positions:
            return 0.0
        return self.positions[symbol].quantity * price
    
    def get_total_value(self, prices: Dict[str, float]) -> float:
        """Get total portfolio value (cash + positions)."""
        positions_value = sum(
            self.get_position_value(symbol, price)
            for symbol, price in prices.items()
            if symbol in self.positions
        )
        return self.cash + positions_value
    
    def is_buy_signal(self, signal_type: str) -> bool:
        """Check if signal is a buy signal."""
        return signal_type in ('STRONG BUY', 'BUY', 'WEAK BUY')
    
    def is_sell_signal(self, signal_type: str) -> bool:
        """Check if signal is a sell signal."""
        return signal_type in ('STRONG SELL', 'SELL', 'WEAK SELL')
    
    def should_exit_position(self, current_signal: str, existing_position: Position) -> bool:
        """Determine if we should exit an existing position based on new signal."""
        # Exit if signal changes direction
        if self.is_buy_signal(existing_position.entry_signal) and self.is_sell_signal(current_signal):
            return True
        if self.is_sell_signal(existing_position.entry_signal) and self.is_buy_signal(current_signal):
            return True
        return False
    
    def execute_buy(
        self,
        symbol: str,
        token_name: str,
        price: float,
        date: datetime,
        signal_type: str,
        total_value: float
    ) -> Optional[Trade]:
        """Execute a buy order."""
        # Calculate position size based on signal strength
        weight = abs(self.SIGNAL_WEIGHTS.get(signal_type, 1.0))
        
        # Allocate percentage of portfolio based on weight
        # Normalize weights so sum of all active positions doesn't exceed 100%
        # For simplicity, we'll use a fixed allocation per signal
        allocation_pct = min(weight * 0.1, 0.2)  # Max 20% per position, scaled by signal strength
        
        trade_value = total_value * allocation_pct
        
        if trade_value > self.cash:
            # Not enough cash, use what we have
            trade_value = self.cash
        
        if trade_value < 1.0:  # Minimum $1 trade
            return None
        
        quantity = trade_value / price
        
        # Execute trade
        self.cash -= trade_value
        
        # Update or create position
        if symbol in self.positions:
            # Add to existing position (average cost)
            existing = self.positions[symbol]
            total_quantity = existing.quantity + quantity
            total_cost = (existing.quantity * existing.entry_price) + trade_value
            avg_price = total_cost / total_quantity
            
            self.positions[symbol] = Position(
                symbol=symbol,
                token_name=token_name,
                quantity=total_quantity,
                entry_price=avg_price,
                entry_date=existing.entry_date,
                entry_signal=existing.entry_signal  # Keep original signal
            )
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                token_name=token_name,
                quantity=quantity,
                entry_price=price,
                entry_date=date,
                entry_signal=signal_type
            )
        
        trade = Trade(
            date=date,
            symbol=symbol,
            token_name=token_name,
            action='BUY',
            quantity=quantity,
            price=price,
            value=trade_value,
            signal_type=signal_type
        )
        
        self.trades.append(trade)
        return trade
    
    def execute_sell(
        self,
        symbol: str,
        token_name: str,
        price: float,
        date: datetime,
        signal_type: str
    ) -> Optional[Trade]:
        """Execute a sell order."""
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        # Sell entire position
        quantity = position.quantity
        trade_value = quantity * price
        
        # Calculate P&L
        entry_value = quantity * position.entry_price
        pnl = trade_value - entry_value
        
        # Execute trade
        self.cash += trade_value
        
        # Remove position
        del self.positions[symbol]
        
        trade = Trade(
            date=date,
            symbol=symbol,
            token_name=token_name,
            action='SELL',
            quantity=quantity,
            price=price,
            value=trade_value,
            signal_type=signal_type,
            pnl=pnl,
            entry_price=position.entry_price
        )
        
        self.trades.append(trade)
        return trade
    
    def process_signal(
        self,
        signal: Signal,
        price: Optional[float],
        current_prices: Dict[str, float]
    ) -> List[Trade]:
        """Process a trading signal and execute trades if needed."""
        trades = []
        
        if price is None:
            print(f"Warning: No price available for {signal.symbol} on {signal.date.strftime('%Y-%m-%d')}")
            return trades
        
        # Get current total portfolio value
        total_value = self.get_total_value(current_prices)
        
        # Check if we have an existing position
        has_position = signal.symbol in self.positions
        
        if has_position:
            existing_position = self.positions[signal.symbol]
            
            # Check if we should exit
            if self.should_exit_position(signal.signal_type, existing_position):
                trade = self.execute_sell(
                    signal.symbol,
                    signal.token_name,
                    price,
                    signal.date,
                    signal.signal_type
                )
                if trade:
                    trades.append(trade)
            
            # If it's a buy signal and we already have a position, we might add to it
            # or if it's a stronger buy signal, we could add more
            elif self.is_buy_signal(signal.signal_type):
                # Only add if new signal is stronger
                current_weight = abs(self.SIGNAL_WEIGHTS.get(existing_position.entry_signal, 1.0))
                new_weight = abs(self.SIGNAL_WEIGHTS.get(signal.signal_type, 1.0))
                
                if new_weight > current_weight:
                    # Add to position with new signal
                    trade = self.execute_buy(
                        signal.symbol,
                        signal.token_name,
                        price,
                        signal.date,
                        signal.signal_type,
                        total_value
                    )
                    if trade:
                        trades.append(trade)
        
        else:
            # No existing position
            if self.is_buy_signal(signal.signal_type):
                # Open new long position
                trade = self.execute_buy(
                    signal.symbol,
                    signal.token_name,
                    price,
                    signal.date,
                    signal.signal_type,
                    total_value
                )
                if trade:
                    trades.append(trade)
            elif self.is_sell_signal(signal.signal_type):
                # SELL signals mean sell existing positions, not short
                # Since we don't have a position, skip it
                pass
        
        return trades
    
    def record_daily_value(self, date: datetime, prices: Dict[str, float]):
        """Record portfolio value for a specific date."""
        total_value = self.get_total_value(prices)
        self.daily_values.append((date, total_value))

