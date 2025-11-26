#!/usr/bin/env python3
"""Fix portfolio state by recalculating daily values using entry price fallback."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.backtest.portfolio import Portfolio
from squid_digest.backtest.portfolio_persistence import PortfolioPersistence


def recalculate_daily_value(
    trades: list,
    date: datetime,
    initial_capital: float
) -> float:
    """Recalculate portfolio value for a specific date using entry prices as fallback.
    
    This simulates what the portfolio value would have been at that date,
    using entry prices for positions that existed at that time.
    """
    # Reconstruct portfolio state up to this date
    temp_portfolio = Portfolio(cash=initial_capital)
    
    # Apply all trades up to and including this date
    for trade in trades:
        if trade.date > date:
            break
        
        if trade.action == 'BUY':
            # Calculate total value at time of trade
            # Use empty dict to trigger entry price fallback for existing positions
            current_prices = {}
            total_value = temp_portfolio.get_total_value(current_prices)
            
            # Execute buy
            temp_portfolio.execute_buy(
                trade.symbol,
                trade.token_name,
                trade.price,
                trade.date,
                trade.signal_type,
                total_value
            )
        elif trade.action == 'SELL':
            temp_portfolio.execute_sell(
                trade.symbol,
                trade.token_name,
                trade.price,
                trade.date,
                trade.signal_type
            )
    
    # Calculate value using entry prices (empty prices dict triggers fallback)
    empty_prices = {}
    return temp_portfolio.get_total_value(empty_prices)


def main():
    """Fix portfolio state by recalculating daily values."""
    # Default state file location
    state_file = Path(__file__).parent.parent / "writeup" / "portfolio_state.json"
    
    if not state_file.exists():
        print(f"Error: State file not found: {state_file}")
        sys.exit(1)
    
    print(f"Loading portfolio state from: {state_file}")
    persistence = PortfolioPersistence(state_file)
    state = persistence.load()
    
    if state is None:
        print("Error: Could not load portfolio state")
        sys.exit(1)
    
    # Create portfolio from state
    portfolio, start_date, initial_capital = persistence.create_portfolio_from_state(state)
    
    print("\n" + "="*80)
    print("FIXING PORTFOLIO STATE")
    print("="*80)
    
    print(f"\nInitial Capital: ${initial_capital:,.2f}")
    print(f"Start Date: {start_date.strftime('%Y-%m-%d')}")
    print(f"Number of trades: {len(portfolio.trades)}")
    print(f"Number of daily values: {len(portfolio.daily_values)}")
    
    # Recalculate all daily values
    print("\nRecalculating daily values using entry price fallback...")
    
    fixed_daily_values = []
    for date, old_value in portfolio.daily_values:
        new_value = recalculate_daily_value(portfolio.trades, date, initial_capital)
        fixed_daily_values.append((date, new_value))
        
        difference = abs(new_value - old_value)
        if difference > 1.0:  # Show if difference is significant
            print(f"  {date.strftime('%Y-%m-%d')}: ${old_value:12,.2f} -> ${new_value:12,.2f} (diff: ${difference:8,.2f})")
    
    # Update portfolio with fixed daily values
    portfolio.daily_values = fixed_daily_values
    
    # Recalculate current portfolio value
    empty_prices = {}
    current_value = portfolio.get_total_value(empty_prices)
    
    print(f"\nCurrent Portfolio Value (recalculated): ${current_value:,.2f}")
    print(f"Cash: ${portfolio.cash:,.2f}")
    
    positions_value = sum(
        pos.quantity * pos.entry_price
        for pos in portfolio.positions.values()
    )
    print(f"Positions Value (at entry): ${positions_value:,.2f}")
    
    # Save fixed state
    print(f"\nSaving fixed portfolio state to: {state_file}")
    persistence.save(portfolio, start_date, initial_capital)
    
    print("\n✓ Portfolio state has been fixed!")
    print("\nNote: Daily values have been recalculated using entry prices as fallback")
    print("      for positions where current prices were unavailable.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
