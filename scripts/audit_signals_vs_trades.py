#!/usr/bin/env python3
"""Audit which signals were received vs which trades were executed."""

import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.backtest.signal_parser import SignalParser
from squid_digest.backtest.portfolio_persistence import PortfolioPersistence


def parse_signals_from_markdown(md_file: Path, writeup_dir: Path) -> list:
    """Parse signals from markdown file."""
    parser = SignalParser(writeup_dir)
    return parser.parse_file(md_file)


def main():
    """Audit signals vs trades."""
    writeup_dir = Path(__file__).parent.parent / "writeup"
    state_file = writeup_dir / "portfolio_state.json"
    
    # Load portfolio state
    persistence = PortfolioPersistence(state_file)
    state = persistence.load()
    
    if state is None:
        print("Error: Could not load portfolio state")
        sys.exit(1)
    
    # Get all trades by date
    trades_by_date = defaultdict(list)
    for trade_data in state['trades']:
        date = datetime.fromisoformat(trade_data['date']).date()
        trades_by_date[date].append(trade_data)
    
    # Get all signal files (recursively search Year/Month/Day subdirectories)
    signal_files = sorted(writeup_dir.rglob("signals_*.md"))
    
    print("="*80)
    print("SIGNALS VS TRADES AUDIT")
    print("="*80)
    
    missing_signals = []
    skipped_signals = []
    
    for signal_file in signal_files:
        # Extract date from filename
        date_str = signal_file.stem.replace("signals_", "")
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        
        # Parse signals from file
        try:
            signals = parse_signals_from_markdown(signal_file, writeup_dir)
        except Exception as e:
            print(f"Warning: Could not parse {signal_file.name}: {e}")
            continue
        
        # Get trades for this date
        trades = trades_by_date.get(file_date, [])
        trade_symbols = {t['symbol'] for t in trades}
        
        print(f"\n{file_date.strftime('%Y-%m-%d')}:")
        print(f"  Signals: {len(signals)}")
        print(f"  Trades executed: {len(trades)}")
        
        # Check each signal
        for signal in signals:
            symbol = signal.symbol
            signal_type = signal.signal_type
            
            if symbol in trade_symbols:
                # Signal resulted in trade
                matching_trades = [t for t in trades if t['symbol'] == symbol]
                for trade in matching_trades:
                    print(f"    ✓ {symbol} {signal_type} -> {trade['action']} {trade['quantity']:.4f} @ ${trade['price']:.2f}")
            else:
                # Signal did NOT result in trade
                print(f"    ✗ {symbol} {signal_type} -> NO TRADE")
                skipped_signals.append({
                    'date': file_date,
                    'symbol': symbol,
                    'signal_type': signal_type,
                    'file': signal_file.name
                })
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nTotal signals that did NOT result in trades: {len(skipped_signals)}")
    
    if skipped_signals:
        print("\nSkipped signals by reason:")
        
        # Group by symbol to see patterns
        by_symbol = defaultdict(list)
        for sig in skipped_signals:
            by_symbol[sig['symbol']].append(sig)
        
        print("\nBy Symbol:")
        for symbol, sigs in sorted(by_symbol.items()):
            print(f"  {symbol}: {len(sigs)} skipped signals")
            for sig in sigs[:3]:  # Show first 3
                print(f"    - {sig['date']}: {sig['signal_type']}")
            if len(sigs) > 3:
                print(f"    ... and {len(sigs) - 3} more")
        
        # Check for SELL signals that were skipped (these are critical!)
        sell_signals_skipped = [s for s in skipped_signals if 'SELL' in s['signal_type']]
        if sell_signals_skipped:
            print(f"\n⚠ CRITICAL: {len(sell_signals_skipped)} SELL signals were skipped!")
            print("These should have exited positions but didn't:")
            for sig in sell_signals_skipped:
                print(f"  - {sig['date']}: {sig['symbol']} {sig['signal_type']}")
    
    return 0 if not skipped_signals else 1


if __name__ == "__main__":
    sys.exit(main())
