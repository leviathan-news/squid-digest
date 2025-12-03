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
    quantity: float  # Positive for long, negative for short
    entry_price: float
    entry_date: datetime
    entry_signal: str  # Signal type that triggered entry
    
    def is_short(self) -> bool:
        """Check if this is a short position."""
        return self.quantity < 0


@dataclass
class Trade:
    """Represents a completed trade."""
    date: datetime
    symbol: str
    token_name: str
    action: str  # 'BUY', 'SELL', 'SHORT', or 'COVER'
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
    strategy: str = 'buy_the_news'  # 'buy_the_news' or 'sell_the_news'
    
    # Signal strength multipliers
    SIGNAL_WEIGHTS = {
        'STRONG BUY': 2.0,
        'BUY': 1.0,
        'WEAK BUY': 0.5,
        'WEAK SELL': -0.5,
        'SELL': -1.0,
        'STRONG SELL': -2.0,
    }
    
    # Signal inversion mapping for sell_the_news strategy
    SIGNAL_INVERSION = {
        'STRONG BUY': 'STRONG SELL',
        'BUY': 'SELL',
        'WEAK BUY': 'WEAK SELL',
        'WEAK SELL': 'WEAK BUY',
        'SELL': 'BUY',
        'STRONG SELL': 'STRONG BUY',
    }
    
    def invert_signal(self, signal_type: str) -> str:
        """Invert a signal type for sell_the_news strategy."""
        if self.strategy == 'sell_the_news':
            return self.SIGNAL_INVERSION.get(signal_type, signal_type)
        return signal_type
    
    def get_position_value(self, symbol: str, price: float) -> float:
        """Get current value of a position.
        
        For longs: quantity * price
        For shorts: -quantity * price (negative value, profit when price goes down)
        """
        if symbol not in self.positions:
            return 0.0
        position = self.positions[symbol]
        if position.is_short():
            # Short position: value is negative, profit when price goes down
            # If we shorted at entry_price and current price is lower, we profit
            return position.quantity * price  # quantity is negative, so this is negative value
        else:
            # Long position: normal value
            return position.quantity * price
    
    def get_total_value(self, prices: Dict[str, float]) -> float:
        """Get total portfolio value (cash + positions).
        
        For longs: adds value to portfolio
        For shorts: we received cash when shorting, but owe tokens (liability)
        Portfolio value = cash - liability (current value of tokens owed)
        
        Uses entry price as fallback when current price is unavailable.
        """
        positions_value = 0.0
        for symbol, position in self.positions.items():
            current_price = prices.get(symbol)
            if current_price is not None:
                if position.is_short():
                    # Short: we owe tokens worth current_value
                    # Liability reduces portfolio value
                    current_value = abs(position.quantity) * current_price
                    positions_value -= current_value  # Subtract liability
                else:
                    # Long: normal value
                    positions_value += position.quantity * current_price
            else:
                # Fallback to entry price if current price unavailable
                if position.is_short():
                    # Short at entry price, assume no change (liability = entry value)
                    entry_value = abs(position.quantity) * position.entry_price
                    positions_value -= entry_value  # Subtract liability
                else:
                    positions_value += position.quantity * position.entry_price
        
        return self.cash + positions_value
    
    def is_buy_signal(self, signal_type: str) -> bool:
        """Check if signal is a buy signal."""
        return signal_type in ('STRONG BUY', 'BUY', 'WEAK BUY')
    
    def is_sell_signal(self, signal_type: str) -> bool:
        """Check if signal is a sell signal."""
        return signal_type in ('STRONG SELL', 'SELL', 'WEAK SELL')
    
    def should_exit_position(self, current_signal: str, existing_position: Position) -> bool:
        """Determine if we should exit an existing position based on new signal.
        
        Note: Both current_signal and existing_position.entry_signal are already
        in the effective form (inverted for sell_the_news strategy if applicable).
        """
        # Exit if signal changes direction
        # For longs: exit on sell signal
        # For shorts: exit on buy signal
        if not existing_position.is_short():
            # Long position: exit on sell signal
            if self.is_buy_signal(existing_position.entry_signal) and self.is_sell_signal(current_signal):
                return True
        else:
            # Short position: exit on buy signal (cover the short)
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
        # Use smaller allocations to prevent exhausting cash too quickly
        # With multiple signals per day, we need to be more conservative
        allocation_pct = min(weight * 0.05, 0.1)  # Max 10% per position, scaled by signal strength (reduced from 20%)
        
        trade_value = total_value * allocation_pct
        
        if trade_value > self.cash:
            # Not enough cash, use what we have
            trade_value = self.cash
        
        if trade_value < 1.0:  # Minimum $1 trade
            return None
        
        quantity = trade_value / price
        
        # Execute trade
        self.cash -= trade_value
        
        # Validation: ensure cash doesn't go negative (shouldn't happen due to check above)
        if self.cash < 0:
            raise ValueError(f"Cash went negative after buy: {self.cash}")
        
        # Update or create position
        if symbol in self.positions:
            existing = self.positions[symbol]
            if existing.is_short():
                # Can't add to short position with buy, skip
                self.cash += trade_value  # Reverse the cash deduction
                return None
            
            # Add to existing long position (average cost)
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
        """Execute a sell order (for long positions)."""
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        # Can only sell long positions
        if position.is_short():
            return None
        
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
    
    def execute_short(
        self,
        symbol: str,
        token_name: str,
        price: float,
        date: datetime,
        signal_type: str,
        total_value: float
    ) -> Optional[Trade]:
        """Execute a short order (sell borrowed tokens)."""
        # Calculate position size based on signal strength
        weight = abs(self.SIGNAL_WEIGHTS.get(signal_type, 1.0))
        
        # Allocate percentage of portfolio based on weight
        # Use smaller allocations to prevent exhausting cash too quickly
        # With multiple signals per day, we need to be more conservative
        allocation_pct = min(weight * 0.05, 0.1)  # Max 10% per position, scaled by signal strength (reduced from 20%)
        
        trade_value = total_value * allocation_pct
        
        if trade_value < 1.0:  # Minimum $1 trade
            return None
        
        quantity = trade_value / price
        
        # Short: we sell borrowed tokens, receive cash
        # Store as negative quantity
        short_quantity = -quantity
        
        # Execute trade: receive cash from selling borrowed tokens
        self.cash += trade_value
        
        # Update or create position
        if symbol in self.positions:
            existing = self.positions[symbol]
            if not existing.is_short():
                # Can't add to long position with short, skip
                self.cash -= trade_value  # Reverse the cash addition
                return None
            
            # Add to existing short position (average entry price)
            total_quantity = existing.quantity + short_quantity  # Both negative
            total_proceeds = (abs(existing.quantity) * existing.entry_price) + trade_value
            avg_price = total_proceeds / abs(total_quantity)
            
            self.positions[symbol] = Position(
                symbol=symbol,
                token_name=token_name,
                quantity=total_quantity,
                entry_price=avg_price,
                entry_date=existing.entry_date,
                entry_signal=existing.entry_signal
            )
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                token_name=token_name,
                quantity=short_quantity,
                entry_price=price,
                entry_date=date,
                entry_signal=signal_type
            )
        
        trade = Trade(
            date=date,
            symbol=symbol,
            token_name=token_name,
            action='SHORT',
            quantity=abs(short_quantity),  # Store as positive for display
            price=price,
            value=trade_value,
            signal_type=signal_type
        )
        
        self.trades.append(trade)
        return trade
    
    def execute_cover(
        self,
        symbol: str,
        token_name: str,
        price: float,
        date: datetime,
        signal_type: str
    ) -> Optional[Trade]:
        """Cover a short position (buy back borrowed tokens)."""
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        # Can only cover short positions
        if not position.is_short():
            return None
        
        # Cover entire short position
        short_quantity = position.quantity  # Negative
        cover_quantity = abs(short_quantity)
        trade_value = cover_quantity * price
        
        # Calculate P&L: we sold at entry_price, buying back at current price
        # Profit if current_price < entry_price
        entry_value = cover_quantity * position.entry_price
        pnl = entry_value - trade_value  # Profit when price drops
        
        # Execute trade: pay cash to buy back tokens
        if trade_value > self.cash:
            # Not enough cash, skip
            return None
        
        self.cash -= trade_value
        
        # Remove position
        del self.positions[symbol]
        
        trade = Trade(
            date=date,
            symbol=symbol,
            token_name=token_name,
            action='COVER',
            quantity=cover_quantity,
            price=price,
            value=trade_value,
            signal_type=signal_type,
            pnl=pnl,
            entry_price=position.entry_price
        )
        
        self.trades.append(trade)
        return trade
    
    def execute_partial_sell(
        self,
        symbol: str,
        token_name: str,
        price: float,
        date: datetime,
        signal_type: str,
        percentage: float = 0.5
    ) -> Optional[Trade]:
        """Execute a partial sell order (for long positions).
        
        Args:
            symbol: Token symbol
            token_name: Token name
            price: Current price
            date: Trade date
            signal_type: Reason for trade (e.g., 'PROFIT_TAKE')
            percentage: Percentage of position to sell (default 0.5 = 50%)
        
        Returns:
            Trade object if successful, None otherwise
        """
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        # Can only sell long positions
        if position.is_short():
            return None
        
        # Sell percentage of position
        sell_quantity = position.quantity * percentage
        trade_value = sell_quantity * price
        
        # Calculate P&L for the portion being sold
        entry_value = sell_quantity * position.entry_price
        pnl = trade_value - entry_value
        
        # Execute trade
        self.cash += trade_value
        
        # Update position: reduce quantity, keep same entry price
        remaining_quantity = position.quantity - sell_quantity
        if remaining_quantity < 0.0001:  # Essentially zero, remove position
            del self.positions[symbol]
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                token_name=token_name,
                quantity=remaining_quantity,
                entry_price=position.entry_price,  # Keep original entry price
                entry_date=position.entry_date,
                entry_signal=position.entry_signal
            )
        
        trade = Trade(
            date=date,
            symbol=symbol,
            token_name=token_name,
            action='SELL',
            quantity=sell_quantity,
            price=price,
            value=trade_value,
            signal_type=signal_type,
            pnl=pnl,
            entry_price=position.entry_price
        )
        
        self.trades.append(trade)
        return trade
    
    def execute_partial_cover(
        self,
        symbol: str,
        token_name: str,
        price: float,
        date: datetime,
        signal_type: str,
        percentage: float = 0.5
    ) -> Optional[Trade]:
        """Execute a partial cover order (for short positions).
        
        Args:
            symbol: Token symbol
            token_name: Token name
            price: Current price
            date: Trade date
            signal_type: Reason for trade (e.g., 'PROFIT_TAKE')
            percentage: Percentage of position to cover (default 0.5 = 50%)
        
        Returns:
            Trade object if successful, None otherwise
        """
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        # Can only cover short positions
        if not position.is_short():
            return None
        
        # Cover percentage of short position
        short_quantity = position.quantity  # Negative
        cover_quantity = abs(short_quantity) * percentage
        trade_value = cover_quantity * price
        
        # Calculate P&L: we sold at entry_price, buying back at current price
        # Profit if current_price < entry_price
        entry_value = cover_quantity * position.entry_price
        pnl = entry_value - trade_value  # Profit when price drops
        
        # Execute trade: pay cash to buy back tokens
        if trade_value > self.cash:
            # Not enough cash, skip
            return None
        
        self.cash -= trade_value
        
        # Update position: reduce quantity, keep same entry price
        remaining_short_quantity = short_quantity + cover_quantity  # Add positive to negative
        if abs(remaining_short_quantity) < 0.0001:  # Essentially zero, remove position
            del self.positions[symbol]
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                token_name=token_name,
                quantity=remaining_short_quantity,
                entry_price=position.entry_price,  # Keep original entry price
                entry_date=position.entry_date,
                entry_signal=position.entry_signal
            )
        
        trade = Trade(
            date=date,
            symbol=symbol,
            token_name=token_name,
            action='COVER',
            quantity=cover_quantity,
            price=price,
            value=trade_value,
            signal_type=signal_type,
            pnl=pnl,
            entry_price=position.entry_price
        )
        
        self.trades.append(trade)
        return trade
    
    def check_stop_loss_and_profit_taking(
        self,
        date: datetime,
        prices: Dict[str, float]
    ) -> List[Trade]:
        """Check all positions for stop loss and profit-taking triggers.
        
        Stop loss: -20% (exit entire position)
        Profit-taking: +20% (sell/cover 50% of position)
        
        Args:
            date: Current date
            prices: Dict of symbol -> current price
        
        Returns:
            List of trades executed
        """
        trades = []
        stop_loss_threshold = -0.20  # -20%
        profit_take_threshold = 0.20  # +20%
        
        # Create a copy of positions dict keys to iterate over
        # (since we may modify positions during iteration)
        symbols_to_check = list(self.positions.keys())
        
        for symbol in symbols_to_check:
            if symbol not in self.positions:
                continue  # Position was already closed
            
            position = self.positions[symbol]
            current_price = prices.get(symbol)
            
            if current_price is None:
                continue  # Skip if no price available
            
            if position.is_short():
                # Short position: profit when price goes down
                # Calculate return: (entry_price - current_price) / entry_price
                # Positive return = profit, negative return = loss
                return_pct = (position.entry_price - current_price) / position.entry_price
                
                if return_pct <= stop_loss_threshold:
                    # Stop loss triggered: price went up 20%+, cover entire position
                    trade = self.execute_cover(
                        symbol,
                        position.token_name,
                        current_price,
                        date,
                        'STOP_LOSS'
                    )
                    if trade:
                        trades.append(trade)
                elif return_pct >= profit_take_threshold:
                    # Profit-taking triggered: price went down 20%+, cover 50%
                    trade = self.execute_partial_cover(
                        symbol,
                        position.token_name,
                        current_price,
                        date,
                        'PROFIT_TAKE',
                        0.5
                    )
                    if trade:
                        trades.append(trade)
            else:
                # Long position: profit when price goes up
                # Calculate return: (current_price - entry_price) / entry_price
                return_pct = (current_price - position.entry_price) / position.entry_price
                
                if return_pct <= stop_loss_threshold:
                    # Stop loss triggered: price went down 20%+, sell entire position
                    trade = self.execute_sell(
                        symbol,
                        position.token_name,
                        current_price,
                        date,
                        'STOP_LOSS'
                    )
                    if trade:
                        trades.append(trade)
                elif return_pct >= profit_take_threshold:
                    # Profit-taking triggered: price went up 20%+, sell 50%
                    trade = self.execute_partial_sell(
                        symbol,
                        position.token_name,
                        current_price,
                        date,
                        'PROFIT_TAKE',
                        0.5
                    )
                    if trade:
                        trades.append(trade)
        
        return trades
    
    def process_signal(
        self,
        signal: Signal,
        price: Optional[float],
        current_prices: Dict[str, float]
    ) -> List[Trade]:
        """Process a trading signal and execute trades if needed.
        
        For SELL signals with existing positions, uses entry price as fallback
        when current price is unavailable.
        """
        trades = []
        
        # Invert signal if using sell_the_news strategy
        effective_signal_type = self.invert_signal(signal.signal_type)
        
        # Get current total portfolio value
        total_value = self.get_total_value(current_prices)
        
        # Check if we have an existing position
        has_position = signal.symbol in self.positions
        
        if has_position:
            existing_position = self.positions[signal.symbol]
            
            # Check if we should exit (using effective signal type)
            if self.should_exit_position(effective_signal_type, existing_position):
                if existing_position.is_short():
                    # Cover short position
                    cover_price = price
                    if cover_price is None:
                        cover_price = existing_position.entry_price
                        print(f"Warning: No price available for {signal.symbol} on {signal.date.strftime('%Y-%m-%d')}, using entry price ${cover_price:.2f} for COVER")
                    
                    trade = self.execute_cover(
                        signal.symbol,
                        signal.token_name,
                        cover_price,
                        signal.date,
                        effective_signal_type
                    )
                    if trade:
                        trades.append(trade)
                else:
                    # Sell long position
                    sell_price = price
                    if sell_price is None:
                        sell_price = existing_position.entry_price
                        print(f"Warning: No price available for {signal.symbol} on {signal.date.strftime('%Y-%m-%d')}, using entry price ${sell_price:.2f} for SELL")
                    
                    trade = self.execute_sell(
                        signal.symbol,
                        signal.token_name,
                        sell_price,
                        signal.date,
                        effective_signal_type
                    )
                    if trade:
                        trades.append(trade)
            
            # If it's a buy signal and we already have a long position, we might add to it
            elif self.is_buy_signal(effective_signal_type) and not existing_position.is_short():
                # Need price for buy - skip if unavailable
                if price is None:
                    print(f"Warning: No price available for {signal.symbol} on {signal.date.strftime('%Y-%m-%d')}, skipping BUY signal")
                    return trades
                
                # Add to position if new signal is same strength or stronger
                # This ensures BUY and SELL strategies remain mirrors
                current_weight = abs(self.SIGNAL_WEIGHTS.get(existing_position.entry_signal, 1.0))
                new_weight = abs(self.SIGNAL_WEIGHTS.get(effective_signal_type, 1.0))
                
                if new_weight >= current_weight:
                    # Add to position with new signal (same or stronger)
                    trade = self.execute_buy(
                        signal.symbol,
                        signal.token_name,
                        price,
                        signal.date,
                        effective_signal_type,
                        total_value
                    )
                    if trade:
                        trades.append(trade)
            
            # If it's a sell signal and we already have a short position, we might add to it
            elif self.is_sell_signal(effective_signal_type) and existing_position.is_short():
                # Need price for short - skip if unavailable
                if price is None:
                    print(f"Warning: No price available for {signal.symbol} on {signal.date.strftime('%Y-%m-%d')}, skipping SHORT signal")
                    return trades
                
                # Add to position if new signal is same strength or stronger
                # This ensures BUY and SELL strategies remain mirrors
                current_weight = abs(self.SIGNAL_WEIGHTS.get(existing_position.entry_signal, 1.0))
                new_weight = abs(self.SIGNAL_WEIGHTS.get(effective_signal_type, 1.0))
                
                if new_weight >= current_weight:
                    # Add to short position with new signal (same or stronger)
                    trade = self.execute_short(
                        signal.symbol,
                        signal.token_name,
                        price,
                        signal.date,
                        effective_signal_type,
                        total_value
                    )
                    if trade:
                        trades.append(trade)
        
        else:
            # No existing position
            if self.is_buy_signal(effective_signal_type):
                # Need price for buy - skip if unavailable
                if price is None:
                    print(f"Warning: No price available for {signal.symbol} on {signal.date.strftime('%Y-%m-%d')}, skipping BUY signal")
                    return trades
                
                # Open new long position
                trade = self.execute_buy(
                    signal.symbol,
                    signal.token_name,
                    price,
                    signal.date,
                    effective_signal_type,
                    total_value
                )
                if trade:
                    trades.append(trade)
            elif self.is_sell_signal(effective_signal_type):
                # SELL signal: open short position
                # Need price for short - skip if unavailable
                if price is None:
                    print(f"Warning: No price available for {signal.symbol} on {signal.date.strftime('%Y-%m-%d')}, skipping SHORT signal")
                    return trades
                
                # Open new short position
                trade = self.execute_short(
                    signal.symbol,
                    signal.token_name,
                    price,
                    signal.date,
                    effective_signal_type,
                    total_value
                )
                if trade:
                    trades.append(trade)
        
        return trades
    
    def record_daily_value(self, date: datetime, prices: Dict[str, float]):
        """Record portfolio value for a specific date.
        
        Also checks for stop loss and profit-taking triggers before recording.
        """
        # Check for stop loss and profit-taking before recording daily value
        self.check_stop_loss_and_profit_taking(date, prices)
        
        total_value = self.get_total_value(prices)
        self.daily_values.append((date, total_value))
    
    def verify_cash_accounting(self, initial_cash: float) -> Dict[str, any]:
        """Verify cash accounting matches trades.
        
        Returns dict with verification results:
        - 'is_valid': bool - whether cash accounting is correct
        - 'expected_cash': float - calculated cash from trades
        - 'actual_cash': float - current cash
        - 'difference': float - difference between expected and actual
        """
        expected_cash = initial_cash
        
        for trade in self.trades:
            if trade.action == 'BUY':
                expected_cash -= trade.value
            elif trade.action == 'SELL':
                expected_cash += trade.value
            elif trade.action == 'SHORT':
                expected_cash += trade.value  # Receive cash from shorting
            elif trade.action == 'COVER':
                expected_cash -= trade.value  # Pay cash to cover
        
        difference = abs(expected_cash - self.cash)
        is_valid = difference < 0.01  # Allow small floating point differences
        
        return {
            'is_valid': is_valid,
            'expected_cash': expected_cash,
            'actual_cash': self.cash,
            'difference': difference
        }


