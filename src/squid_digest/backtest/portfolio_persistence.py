"""Portfolio persistence for incremental backtesting."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from .portfolio import Portfolio, Position, Trade


class PortfolioPersistence:
    """Save and load portfolio state to/from JSON."""
    
    def __init__(self, state_file: Path):
        """Initialize with state file path."""
        self.state_file = Path(state_file)
    
    def save(self, portfolio: Portfolio, start_date: datetime, initial_capital: float) -> None:
        """Save portfolio state to JSON file."""
        # Convert positions to dict
        positions_dict = {}
        for symbol, position in portfolio.positions.items():
            positions_dict[symbol] = {
                'symbol': position.symbol,
                'token_name': position.token_name,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'entry_date': position.entry_date.isoformat(),
                'entry_signal': position.entry_signal,
            }
        
        # Convert trades to list of dicts
        trades_list = []
        for trade in portfolio.trades:
            trades_list.append({
                'date': trade.date.isoformat(),
                'symbol': trade.symbol,
                'token_name': trade.token_name,
                'action': trade.action,
                'quantity': trade.quantity,
                'price': trade.price,
                'value': trade.value,
                'signal_type': trade.signal_type,
                'pnl': trade.pnl,
                'entry_price': trade.entry_price,
            })
        
        # Convert daily values to list of [date_str, value]
        daily_values_list = [
            [date.isoformat(), value]
            for date, value in portfolio.daily_values
        ]
        
        state = {
            'start_date': start_date.isoformat(),
            'initial_capital': initial_capital,
            'cash': portfolio.cash,
            'positions': positions_dict,
            'trades': trades_list,
            'daily_values': daily_values_list,
            'strategy': portfolio.strategy,
        }
        
        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to file
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load(self) -> Optional[dict]:
        """Load portfolio state from JSON file."""
        if not self.state_file.exists():
            return None
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            return state
        except Exception as e:
            print(f"Warning: Could not load portfolio state from {self.state_file}: {e}")
            return None
    
    def create_portfolio_from_state(self, state: dict) -> Tuple[Portfolio, datetime, float]:
        """Create Portfolio object from loaded state."""
        # Parse start date and initial capital
        start_date = datetime.fromisoformat(state['start_date'])
        initial_capital = state['initial_capital']
        
        # Create portfolio
        strategy = state.get('strategy', 'buy_the_news')  # Default for backward compatibility
        portfolio = Portfolio(cash=state['cash'], strategy=strategy)
        
        # Restore positions
        for symbol, pos_data in state['positions'].items():
            portfolio.positions[symbol] = Position(
                symbol=pos_data['symbol'],
                token_name=pos_data['token_name'],
                quantity=pos_data['quantity'],
                entry_price=pos_data['entry_price'],
                entry_date=datetime.fromisoformat(pos_data['entry_date']),
                entry_signal=pos_data['entry_signal'],
            )
        
        # Restore trades
        for trade_data in state['trades']:
            portfolio.trades.append(Trade(
                date=datetime.fromisoformat(trade_data['date']),
                symbol=trade_data['symbol'],
                token_name=trade_data['token_name'],
                action=trade_data['action'],
                quantity=trade_data['quantity'],
                price=trade_data['price'],
                value=trade_data['value'],
                signal_type=trade_data['signal_type'],
                pnl=trade_data.get('pnl'),
                entry_price=trade_data.get('entry_price'),
            ))
        
        # Restore daily values
        for date_str, value in state['daily_values']:
            date = datetime.fromisoformat(date_str)
            portfolio.daily_values.append((date, value))
        
        return portfolio, start_date, initial_capital

