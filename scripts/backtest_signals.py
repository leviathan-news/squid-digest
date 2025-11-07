#!/usr/bin/env python3
"""Backtest trading signals from markdown files."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.backtest.metrics import MetricsCalculator
from squid_digest.backtest.portfolio import Portfolio
from squid_digest.backtest.price_fetcher import PriceFetcher
from squid_digest.backtest.signal_parser import SignalParser
from squid_digest.config import WRITEUP_DIR


def main():
    """Run the backtest."""
    # Configuration
    initial_capital = 10000.0
    start_date = datetime(2025, 10, 17)
    end_date = datetime(2025, 11, 3)
    
    print("=" * 60)
    print("BACKTESTING TRADING SIGNALS")
    print("=" * 60)
    print(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print()
    
    # Step 1: Parse signals
    print("Step 1: Parsing signals from markdown files...")
    parser = SignalParser(WRITEUP_DIR)
    signals = parser.parse_date_range(start_date, end_date)
    print(f"Found {len(signals)} signals")
    
    if not signals:
        print("No signals found. Exiting.")
        return
    
    # Group signals by date for processing
    signals_by_date = {}
    for signal in signals:
        date_key = signal.date.strftime('%Y-%m-%d')
        if date_key not in signals_by_date:
            signals_by_date[date_key] = []
        signals_by_date[date_key].append(signal)
    
    # Step 2: Initialize portfolio and price fetcher
    print("\nStep 2: Initializing portfolio and price fetcher...")
    portfolio = Portfolio(cash=initial_capital)
    # Use CoinGecko API key to avoid rate limits
    price_fetcher = PriceFetcher(coingecko_api_key="CG-5pNpnHzumZtbhZmjQ6NXJmis")
    
    # Step 3: Process signals chronologically
    print("\nStep 3: Processing signals and executing trades...")
    
    # Get all unique dates
    all_dates = sorted(set(s.date for s in signals))
    all_dates.append(end_date)  # Add end date for final valuation
    
    # Track current prices for all tokens we're interested in
    token_symbols = sorted(set(s.symbol for s in signals))
    
    # Pre-fetch prices for all tokens across the date range
    print("  Pre-fetching prices...")
    price_cache = {}
    for symbol in token_symbols:
        coingecko_id = price_fetcher.get_coingecko_id(symbol)
        if coingecko_id:
            prices = price_fetcher.fetch_price_history(coingecko_id, start_date, end_date)
            price_cache[symbol] = prices
            print(f"    {symbol}: {len(prices)} prices")
        else:
            print(f"    {symbol}: No CoinGecko ID found, skipping")
    
    for current_date in all_dates:
        # Get current prices for all tokens from cache
        current_prices = {}
        date_key = current_date.strftime('%Y-%m-%d')
        
        for symbol in token_symbols:
            if symbol in price_cache:
                # Try exact date, then previous day, then next day
                if date_key in price_cache[symbol]:
                    current_prices[symbol] = price_cache[symbol][date_key]
                else:
                    # Try previous day
                    prev_key = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
                    if prev_key in price_cache[symbol]:
                        current_prices[symbol] = price_cache[symbol][prev_key]
                    else:
                        # Try next day
                        next_key = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
                        if next_key in price_cache[symbol]:
                            current_prices[symbol] = price_cache[symbol][next_key]
        
        # Process signals for this date
        if date_key in signals_by_date:
            for signal in signals_by_date[date_key]:
                # Get price for signal date
                signal_date_key = signal.date.strftime('%Y-%m-%d')
                price = None
                
                if signal.symbol in price_cache:
                    if signal_date_key in price_cache[signal.symbol]:
                        price = price_cache[signal.symbol][signal_date_key]
                    else:
                        # Try nearby dates
                        for offset in [-1, 1]:
                            try_key = (signal.date + timedelta(days=offset)).strftime('%Y-%m-%d')
                            if try_key in price_cache[signal.symbol]:
                                price = price_cache[signal.symbol][try_key]
                                break
                
                trades = portfolio.process_signal(signal, price, current_prices)
                
                if trades:
                    for trade in trades:
                        action_str = f"{trade.action:4s} {trade.quantity:.4f} {trade.symbol:6s} @ ${trade.price:.2f}"
                        if trade.pnl is not None:
                            pnl_str = f" (P&L: ${trade.pnl:+.2f})"
                        else:
                            pnl_str = ""
                        print(f"  {signal.date.strftime('%Y-%m-%d')}: {action_str}{pnl_str}")
        
        # Record daily portfolio value
        portfolio.record_daily_value(current_date, current_prices)
    
    # Close price fetcher
    price_fetcher.close()
    
    # Step 4: Calculate metrics
    print("\nStep 4: Calculating performance metrics...")
    metrics = MetricsCalculator(portfolio, initial_capital)
    
    total_return = metrics.total_return()
    sharpe = metrics.sharpe_ratio()
    win_rate = metrics.win_rate()
    total_trades = metrics.total_trades()
    total_pnl = metrics.total_pnl()
    best_trade = metrics.best_trade()
    worst_trade = metrics.worst_trade()
    avg_pnl = metrics.average_trade_pnl()
    max_dd = metrics.max_drawdown()
    
    # Step 5: Print summary
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Initial Capital:      ${initial_capital:,.2f}")
    
    if portfolio.daily_values:
        final_value = portfolio.daily_values[-1][1]
        print(f"Final Value:           ${final_value:,.2f}")
        print(f"Total Return:         {total_return:+.2f}%")
    
    print(f"Total Trades:         {total_trades}")
    print(f"Total P&L:            ${total_pnl:+,.2f}")
    
    if avg_pnl is not None:
        print(f"Average P&L/Trade:    ${avg_pnl:+,.2f}")
    
    if win_rate is not None:
        print(f"Win Rate:             {win_rate:.1f}%")
    
    if sharpe is not None:
        print(f"Sharpe Ratio:         {sharpe:.2f}")
    
    if max_dd:
        dd_pct, dd_start, dd_end = max_dd
        print(f"Max Drawdown:         {dd_pct:.2f}%")
        if dd_start and dd_end:
            print(f"  From: {dd_start.strftime('%Y-%m-%d')} to {dd_end.strftime('%Y-%m-%d')}")
    
    if best_trade:
        print(f"\nBest Trade:")
        print(f"  {best_trade.date.strftime('%Y-%m-%d')}: SELL {best_trade.quantity:.4f} {best_trade.symbol} @ ${best_trade.price:.2f}")
        print(f"  P&L: ${best_trade.pnl:+,.2f}")
    
    if worst_trade:
        print(f"\nWorst Trade:")
        print(f"  {worst_trade.date.strftime('%Y-%m-%d')}: SELL {worst_trade.quantity:.4f} {worst_trade.symbol} @ ${worst_trade.price:.2f}")
        print(f"  P&L: ${worst_trade.pnl:+,.2f}")
    
    # Step 6: Generate report
    print("\nStep 5: Generating detailed report...")
    from squid_digest.backtest.report import ReportGenerator
    
    report_gen = ReportGenerator(portfolio, metrics, signals, initial_capital, start_date, end_date)
    report_path = report_gen.generate_report(WRITEUP_DIR)
    
    print(f"\nDetailed report saved to: {report_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()

