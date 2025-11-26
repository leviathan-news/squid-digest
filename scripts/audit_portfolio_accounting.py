#!/usr/bin/env python3
"""Audit portfolio accounting to verify cash and portfolio value calculations."""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.backtest.portfolio import Portfolio
from squid_digest.backtest.portfolio_persistence import PortfolioPersistence


def main():
    """Run portfolio accounting audit."""
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
    print("PORTFOLIO ACCOUNTING AUDIT")
    print("="*80)
    
    # 1. Cash Reconciliation
    print("\n1. CASH RECONCILIATION")
    print("-" * 80)
    cash_verification = portfolio.verify_cash_accounting(initial_capital)
    
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Expected Cash (from trades): ${cash_verification['expected_cash']:,.2f}")
    print(f"Actual Cash: ${cash_verification['actual_cash']:,.2f}")
    print(f"Difference: ${cash_verification['difference']:,.2f}")
    
    if cash_verification['is_valid']:
        print("✓ Cash accounting is CORRECT")
    else:
        print("✗ Cash accounting MISMATCH detected!")
    
    # Calculate total buy/sell values
    total_buys = sum(t.value for t in portfolio.trades if t.action == 'BUY')
    total_sells = sum(t.value for t in portfolio.trades if t.action == 'SELL')
    print(f"\nTotal Buys: ${total_buys:,.2f}")
    print(f"Total Sells: ${total_sells:,.2f}")
    print(f"Net Cash Flow: ${total_sells - total_buys:,.2f}")
    
    # 2. Position Value Verification
    print("\n2. POSITION VALUE VERIFICATION")
    print("-" * 80)
    
    # Calculate position values using entry prices (fallback)
    positions_value_at_entry = 0.0
    print("\nCurrent Positions:")
    for symbol, position in portfolio.positions.items():
        entry_value = position.quantity * position.entry_price
        positions_value_at_entry += entry_value
        print(f"  {symbol:6s}: {position.quantity:15.8f} @ ${position.entry_price:10.2f} = ${entry_value:12.2f}")
    
    print(f"\nTotal Positions Value (at entry): ${positions_value_at_entry:,.2f}")
    print(f"Cash: ${portfolio.cash:,.2f}")
    print(f"Expected Portfolio Value: ${portfolio.cash + positions_value_at_entry:,.2f}")
    
    # 3. Portfolio Value Verification (using entry prices as fallback)
    print("\n3. PORTFOLIO VALUE VERIFICATION")
    print("-" * 80)
    
    # Use empty prices dict to trigger fallback to entry prices
    empty_prices = {}
    calculated_value = portfolio.get_total_value(empty_prices)
    
    print(f"Calculated Portfolio Value (entry price fallback): ${calculated_value:,.2f}")
    
    # Check last recorded daily value
    if portfolio.daily_values:
        last_date, last_value = portfolio.daily_values[-1]
        print(f"Last Recorded Daily Value ({last_date.strftime('%Y-%m-%d')}): ${last_value:,.2f}")
        
        difference = abs(calculated_value - last_value)
        print(f"Difference: ${difference:,.2f}")
        
        if difference > 100:  # Threshold for significant difference
            print(f"⚠ WARNING: Large difference detected! This suggests missing prices were not handled correctly.")
        else:
            print("✓ Portfolio value matches expected (within threshold)")
    
    # 4. Detect Sudden Drops in Daily Values
    print("\n4. DAILY VALUES ANALYSIS")
    print("-" * 80)
    
    if len(portfolio.daily_values) > 1:
        print("\nDaily Value Changes:")
        prev_value = None
        for date, value in portfolio.daily_values:
            if prev_value is not None:
                change = value - prev_value
                change_pct = (change / prev_value) * 100 if prev_value > 0 else 0
                marker = "⚠" if abs(change_pct) > 20 else " "
                print(f"{marker} {date.strftime('%Y-%m-%d')}: ${value:12,.2f} (change: ${change:8,.2f}, {change_pct:+6.2f}%)")
            else:
                print(f"   {date.strftime('%Y-%m-%d')}: ${value:12,.2f} (initial)")
            prev_value = value
        
        # Check for suspicious drops
        max_drop = 0
        drop_date = None
        for i in range(1, len(portfolio.daily_values)):
            prev_value = portfolio.daily_values[i-1][1]
            curr_value = portfolio.daily_values[i][1]
            drop_pct = ((prev_value - curr_value) / prev_value) * 100 if prev_value > 0 else 0
            if drop_pct > max_drop:
                max_drop = drop_pct
                drop_date = portfolio.daily_values[i][0]
        
        if max_drop > 20:
            print(f"\n⚠ WARNING: Largest single-day drop: {max_drop:.2f}% on {drop_date.strftime('%Y-%m-%d')}")
            print("  This may indicate missing prices were not handled correctly.")
    
    # 5. Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    issues = []
    if not cash_verification['is_valid']:
        issues.append("Cash accounting mismatch")
    
    if portfolio.daily_values:
        last_date, last_value = portfolio.daily_values[-1]
        if abs(calculated_value - last_value) > 100:
            issues.append("Portfolio value mismatch (likely missing prices)")
    
    if max_drop > 20:
        issues.append(f"Large daily value drop detected ({max_drop:.2f}%)")
    
    if issues:
        print("\n✗ ISSUES DETECTED:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nRecommendation: Run fix_portfolio_state.py to correct historical values")
        return 1
    else:
        print("\n✓ No issues detected. Portfolio accounting is correct.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
