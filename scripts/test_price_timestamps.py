#!/usr/bin/env python3
"""
Test script to verify price timestamps from CoinGecko.
This script only reads prices and displays timestamps - it doesn't generate trades,
write files, or post anything.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from squid_digest.backtest.price_fetcher import PriceFetcher

def main():
    print("=" * 60)
    print("Price Timestamp Verification Test")
    print("=" * 60)
    print()
    
    # Test a few common tokens
    test_symbols = ["BTC", "ETH", "SOL", "ADA"]
    
    price_fetcher = PriceFetcher()
    today = datetime.now()
    
    print(f"Testing price timestamps for: {today.strftime('%Y-%m-%d')}")
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    for symbol in test_symbols:
        print(f"\n{symbol}:")
        print("-" * 40)
        
        coingecko_id = price_fetcher.get_coingecko_id(symbol)
        if not coingecko_id:
            print(f"  ❌ Could not find CoinGecko ID for {symbol}")
            continue
        
        print(f"  CoinGecko ID: {coingecko_id}")
        
        # Fetch price for today
        price = price_fetcher.get_price(symbol, today)
        
        if price:
            print(f"  ✅ Price: ${price:,.2f}")
            print(f"  ⚠️  Note: Check the logs above for the actual timestamp")
        else:
            print(f"  ❌ Could not fetch price for {symbol}")
    
    print()
    print("=" * 60)
    print("Check the output above for 'Today's price timestamp' lines")
    print("The timestamp should be AFTER the news typically breaks (after ~12:00 UTC)")
    print("=" * 60)
    
    price_fetcher.close()

if __name__ == "__main__":
    main()
