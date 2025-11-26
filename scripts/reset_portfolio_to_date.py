#!/usr/bin/env python3
"""Reset portfolio state files to remove trades from a specific date.

This is used to undo a bad run and allow rerunning with correct data.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.backtest.portfolio import Portfolio
from squid_digest.backtest.portfolio_persistence import PortfolioPersistence
from squid_digest.config import (
    BACKTEST_PORTFOLIO_STATE_FILE_BUY,
    BACKTEST_PORTFOLIO_STATE_FILE_SELL,
)


def reset_portfolio_state(state_file: Path, reset_date: str) -> bool:
    """Remove all trades and positions from reset_date onwards.
    
    Args:
        state_file: Path to portfolio state file
        reset_date: Date string (YYYY-MM-DD) to reset to (removes this date and later)
        
    Returns:
        True if successful, False otherwise
    """
    if not state_file.exists():
        print(f"Warning: State file not found: {state_file}")
        return False
    
    print(f"\nProcessing: {state_file.name}")
    persistence = PortfolioPersistence(state_file)
    state = persistence.load()
    
    if state is None:
        print(f"Error: Could not load portfolio state from {state_file}")
        return False
    
    reset_datetime = datetime.fromisoformat(f"{reset_date}T00:00:00")
    
    # Filter out trades from reset_date onwards
    original_trade_count = len(state['trades'])
    state['trades'] = [
        trade for trade in state['trades']
        if datetime.fromisoformat(trade['date']) < reset_datetime
    ]
    removed_trades = original_trade_count - len(state['trades'])
    
    # Filter out positions entered on or after reset_date
    original_position_count = len(state['positions'])
    state['positions'] = {
        symbol: pos for symbol, pos in state['positions'].items()
        if datetime.fromisoformat(pos['entry_date']) < reset_datetime
    }
    removed_positions = original_position_count - len(state['positions'])
    
    # Filter out daily values from reset_date onwards
    original_daily_count = len(state['daily_values'])
    state['daily_values'] = [
        [date_str, value] for date_str, value in state['daily_values']
        if datetime.fromisoformat(date_str) < reset_datetime
    ]
    removed_daily = original_daily_count - len(state['daily_values'])
    
    # Recreate portfolio from cleaned state to recalculate cash
    portfolio, start_date, initial_capital = persistence.create_portfolio_from_state(state)
    
    # Update cash in state
    state['cash'] = portfolio.cash
    
    print(f"  Removed {removed_trades} trades")
    print(f"  Removed {removed_positions} positions")
    print(f"  Removed {removed_daily} daily value entries")
    print(f"  Updated cash: ${state['cash']:,.2f}")
    
    # Save cleaned state
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)
    
    print(f"  ✓ Saved cleaned state to {state_file}")
    return True


def main():
    """Reset portfolio state files to remove today's trades."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/reset_portfolio_to_date.py YYYY-MM-DD")
        print("Example: python scripts/reset_portfolio_to_date.py 2025-11-23")
        sys.exit(1)
    
    reset_date = sys.argv[1]
    try:
        # Validate date format
        datetime.fromisoformat(f"{reset_date}T00:00:00")
    except ValueError:
        print(f"Error: Invalid date format: {reset_date}")
        print("Expected format: YYYY-MM-DD")
        sys.exit(1)
    
    print("=" * 80)
    print(f"RESETTING PORTFOLIO STATE - Removing all data from {reset_date} onwards")
    print("=" * 80)
    
    success = True
    success &= reset_portfolio_state(BACKTEST_PORTFOLIO_STATE_FILE_BUY, reset_date)
    success &= reset_portfolio_state(BACKTEST_PORTFOLIO_STATE_FILE_SELL, reset_date)
    
    if success:
        print("\n" + "=" * 80)
        print("✓ Portfolio state files have been reset!")
        print(f"  All trades, positions, and daily values from {reset_date} onwards have been removed.")
        print("  You can now rerun the workflow to regenerate with correct data.")
        print("=" * 80)
        return 0
    else:
        print("\n✗ Some errors occurred while resetting portfolio state")
        return 1


if __name__ == "__main__":
    sys.exit(main())
