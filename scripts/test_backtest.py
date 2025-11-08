#!/usr/bin/env python3
"""Test script for incremental backtest functionality."""

import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from squid_digest.backtest.incremental_backtest import IncrementalBacktest
from squid_digest.backtest.signal_parser import Signal, SignalParser
from squid_digest.backtest.newsletter_formatter import format_backtest_for_newsletter
from squid_digest.config import (
    WRITEUP_DIR,
    BACKTEST_INITIAL_CAPITAL,
    BACKTEST_PORTFOLIO_STATE_FILE
)


def test_portfolio_persistence():
    """Test portfolio save/load functionality."""
    print("=" * 60)
    print("TEST 1: Portfolio Persistence")
    print("=" * 60)
    
    from squid_digest.backtest.portfolio_persistence import PortfolioPersistence
    from squid_digest.backtest.portfolio import Portfolio
    
    # Create test portfolio
    portfolio = Portfolio(cash=10000.0)
    start_date = datetime.now()
    
    # Save
    persistence = PortfolioPersistence(BACKTEST_PORTFOLIO_STATE_FILE)
    persistence.save(portfolio, start_date, BACKTEST_INITIAL_CAPITAL)
    print(f"✓ Saved portfolio state to {BACKTEST_PORTFOLIO_STATE_FILE}")
    
    # Load
    state = persistence.load()
    if state:
        print(f"✓ Loaded portfolio state")
        print(f"  - Start date: {state['start_date']}")
        print(f"  - Initial capital: ${state['initial_capital']:,.2f}")
        print(f"  - Cash: ${state['cash']:,.2f}")
        print(f"  - Positions: {len(state['positions'])}")
        print(f"  - Trades: {len(state['trades'])}")
    else:
        print("✗ Failed to load portfolio state")
        return False
    
    # Recreate portfolio from state
    portfolio2, start_date2, initial_capital2 = persistence.create_portfolio_from_state(state)
    print(f"✓ Recreated portfolio from state")
    print(f"  - Cash: ${portfolio2.cash:,.2f}")
    print(f"  - Positions: {len(portfolio2.positions)}")
    print(f"  - Trades: {len(portfolio2.trades)}")
    
    return True


def test_signal_parsing():
    """Test signal parsing from existing signals file."""
    print("\n" + "=" * 60)
    print("TEST 2: Signal Parsing")
    print("=" * 60)
    
    # Find most recent signals file
    signal_files = sorted(WRITEUP_DIR.glob("signals_*.md"), reverse=True)
    
    if not signal_files:
        print("⚠ No signals files found. Skipping signal parsing test.")
        print("  (This is OK if you haven't generated signals yet)")
        return True
    
    latest_file = signal_files[0]
    print(f"Testing with: {latest_file.name}")
    
    parser = SignalParser(WRITEUP_DIR)
    signals = parser.parse_file(latest_file)
    
    print(f"✓ Parsed {len(signals)} signals")
    for i, signal in enumerate(signals[:3], 1):  # Show first 3
        print(f"  {i}. {signal.symbol} - {signal.signal_type}")
    
    if len(signals) > 3:
        print(f"  ... and {len(signals) - 3} more")
    
    return len(signals) > 0


def test_incremental_backtest():
    """Test incremental backtest with sample signals."""
    print("\n" + "=" * 60)
    print("TEST 3: Incremental Backtest")
    print("=" * 60)
    
    # Create sample signals for testing
    today = datetime.now()
    test_signals = [
        Signal(
            date=today,
            symbol="BTC",
            token_name="Bitcoin",
            signal_type="BUY",
            reason="Test signal"
        ),
        Signal(
            date=today,
            symbol="ETH",
            token_name="Ethereum",
            signal_type="WEAK BUY",
            reason="Test signal"
        ),
    ]
    
    print(f"Testing with {len(test_signals)} sample signals")
    print(f"Date: {today.strftime('%Y-%m-%d')}")
    
    try:
        backtest = IncrementalBacktest(
            state_file=BACKTEST_PORTFOLIO_STATE_FILE,
            writeup_dir=WRITEUP_DIR,
            initial_capital=BACKTEST_INITIAL_CAPITAL
        )
        
        print("Running backtest...")
        results = backtest.run(today, test_signals)
        backtest.close()
        
        if not results:
            print("✗ Backtest returned no results")
            return False
        
        print("✓ Backtest completed")
        print(f"  - Portfolio value: ${results['portfolio_value']:,.2f}")
        print(f"  - Total return: {results['total_return']:+.2f}%")
        print(f"  - Days since start: {results['days_since_start']}")
        print(f"  - Positions: {len(results['positions'])}")
        print(f"  - Trades today: {len(results['trades_today'])}")
        
        # VALIDATE that prices were fetched and benchmarks work
        benchmark_returns = results['benchmark_returns']
        btc_bench = benchmark_returns.get('BTC')
        btc_eth_bench = benchmark_returns.get('BTC_ETH')
        
        print(f"  - Benchmark BTC: {btc_bench if btc_bench is not None else 'None (FAILED)'}")
        print(f"  - Benchmark BTC+ETH: {btc_eth_bench if btc_eth_bench is not None else 'None (FAILED)'}")
        
        # For same-day tests, benchmarks might be 0% which is OK, but None is a failure
        if btc_bench is None and btc_eth_bench is None:
            print("✗ CRITICAL: No benchmark prices fetched - price fetching is broken!")
            print("  This means CoinGecko API calls are failing or API key is missing")
            return False
        
        # Test formatting
        formatted = format_backtest_for_newsletter(results)
        print(f"  - Formatted length: {len(formatted)} characters")
        print("\nSample formatted output:")
        print("-" * 60)
        print(formatted[:500] + "..." if len(formatted) > 500 else formatted)
        print("-" * 60)
        
        return True
            
    except Exception as e:
        print(f"✗ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_real_signals():
    """Test backtest with real signals from latest file."""
    print("\n" + "=" * 60)
    print("TEST 4: Backtest with Real Signals")
    print("=" * 60)
    
    # Find most recent signals file
    signal_files = sorted(WRITEUP_DIR.glob("signals_*.md"), reverse=True)
    
    if not signal_files:
        print("⚠ No signals files found. Skipping real signals test.")
        return True
    
    latest_file = signal_files[0]
    print(f"Using signals from: {latest_file.name}")
    
    parser = SignalParser(WRITEUP_DIR)
    signals = parser.parse_file(latest_file)
    
    if not signals:
        print("⚠ No signals found in file. Skipping.")
        return True
    
    print(f"Found {len(signals)} signals")
    
    try:
        backtest = IncrementalBacktest(
            state_file=BACKTEST_PORTFOLIO_STATE_FILE,
            writeup_dir=WRITEUP_DIR,
            initial_capital=BACKTEST_INITIAL_CAPITAL
        )
        
        # Use today's date, not the signal date (signals might be from the past)
        # The backtest should process signals for the current date
        today = datetime.now()
        signal_date = signals[0].date
        
        # Always use today's date for testing (signals from past dates won't work
        # if portfolio was started after the signal date)
        test_date = today
        if signal_date != today:
            print(f"⚠ Signal date {signal_date.date()} differs from today, using today ({today.date()}) for backtest")
        
        print(f"Running backtest for date: {test_date.strftime('%Y-%m-%d')}")
        results = backtest.run(test_date, signals)
        backtest.close()
        
        if not results:
            print("✗ Backtest returned no results")
            return False
        
        print("✓ Backtest completed")
        print(f"  - Portfolio value: ${results['portfolio_value']:,.2f}")
        print(f"  - Total return: {results['total_return']:+.2f}%")
        
        # VALIDATE benchmarks - this is the critical check
        benchmark_returns = results['benchmark_returns']
        btc_bench = benchmark_returns.get('BTC')
        btc_eth_bench = benchmark_returns.get('BTC_ETH')
        btc_eth_open_bench = benchmark_returns.get('BTC_ETH_OPEN')
        
        print(f"  - Benchmark BTC: {btc_bench if btc_bench is not None else 'None (FAILED)'}")
        print(f"  - Benchmark BTC+ETH: {btc_eth_bench if btc_eth_bench is not None else 'None (FAILED)'}")
        print(f"  - Benchmark BTC+ETH+OPEN: {btc_eth_open_bench if btc_eth_open_bench is not None else 'None (FAILED)'}")
        
        # Check if benchmarks were calculated
        if btc_bench is None and btc_eth_bench is None and btc_eth_open_bench is None:
            print("✗ ALL BENCHMARKS FAILED - This is a critical failure!")
            print("  Check:")
            print("  1. CoinGecko API key is set")
            print("  2. Price fetching is working")
            print("  3. Date range is valid (start_date <= current_date)")
            return False
        
        # At least one benchmark should work
        if btc_bench is None:
            print("⚠ BTC benchmark failed (but others may have worked)")
        if btc_eth_bench is None:
            print("⚠ BTC+ETH benchmark failed (but others may have worked)")
        if btc_eth_open_bench is None:
            print("⚠ BTC+ETH+OPEN benchmark failed (OPEN token ID might be wrong)")
        
        return True
            
    except Exception as e:
        print(f"✗ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling():
    """Test error handling with invalid inputs."""
    print("\n" + "=" * 60)
    print("TEST 5: Error Handling")
    print("=" * 60)
    
    # Test with empty signals
    print("Testing with empty signals list...")
    try:
        backtest = IncrementalBacktest(
            state_file=BACKTEST_PORTFOLIO_STATE_FILE,
            writeup_dir=WRITEUP_DIR,
            initial_capital=BACKTEST_INITIAL_CAPITAL
        )
        
        results = backtest.run(datetime.now(), [])
        backtest.close()
        
        if not results:
            print("✗ Backtest returned None - should return results even with empty signals")
            return False
        
        # Even with empty signals, benchmarks should still work
        benchmark_returns = results.get('benchmark_returns', {})
        btc_bench = benchmark_returns.get('BTC')
        
        if btc_bench is None:
            print("✗ CRITICAL: Benchmarks failed even with empty signals - price fetching is broken!")
            return False
        
        print("✓ Handled empty signals gracefully")
        print(f"  - Benchmarks still work: BTC = {btc_bench:+.2f}%")
        return True
    except Exception as e:
        print(f"✗ Failed with empty signals: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("BACKTEST TESTING SUITE")
    print("=" * 60)
    print(f"Portfolio state file: {BACKTEST_PORTFOLIO_STATE_FILE}")
    print(f"Initial capital: ${BACKTEST_INITIAL_CAPITAL:,.2f}")
    print()
    
    tests = [
        ("Portfolio Persistence", test_portfolio_persistence),
        ("Signal Parsing", test_signal_parsing),
        ("Incremental Backtest", test_incremental_backtest),
        ("Real Signals Test", test_with_real_signals),
        ("Error Handling", test_error_handling),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Ready for GitHub Actions.")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

