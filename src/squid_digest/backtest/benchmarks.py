"""Calculate benchmark returns for portfolio comparison."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from .price_fetcher import PriceFetcher

logger = logging.getLogger(__name__)


class BenchmarkCalculator:
    """Calculate benchmark portfolio returns."""
    
    # CoinGecko IDs for benchmarks
    BTC_ID = 'bitcoin'
    ETH_ID = 'ethereum'
    OPEN_ID = 'open-stablecoin-index'  # From the URL provided
    
    def __init__(self, price_fetcher: PriceFetcher):
        """Initialize with price fetcher."""
        self.price_fetcher = price_fetcher
    
    def get_benchmark_prices(
        self,
        start_date: datetime,
        current_date: datetime
    ) -> Dict[str, Dict[str, float]]:
        """Fetch prices for all benchmark tokens.
        
        Returns:
            Dict with keys 'BTC', 'ETH', 'OPEN', each containing dict of {date_str: price}
        """
        prices = {}
        
        # Fetch BTC prices
        try:
            btc_prices = self.price_fetcher.fetch_price_history(
                self.BTC_ID, start_date, current_date
            )
            prices['BTC'] = btc_prices
            if not btc_prices:
                logger.warning(f"No BTC prices fetched for date range {start_date.date()} to {current_date.date()}")
        except Exception as e:
            logger.warning(f"Failed to fetch BTC prices: {e}")
            prices['BTC'] = {}
        
        # Fetch ETH prices
        try:
            eth_prices = self.price_fetcher.fetch_price_history(
                self.ETH_ID, start_date, current_date
            )
            prices['ETH'] = eth_prices
            if not eth_prices:
                logger.warning(f"No ETH prices fetched for date range {start_date.date()} to {current_date.date()}")
        except Exception as e:
            logger.warning(f"Failed to fetch ETH prices: {e}")
            prices['ETH'] = {}
        
        # Fetch OPEN prices
        try:
            open_prices = self.price_fetcher.fetch_price_history(
                self.OPEN_ID, start_date, current_date
            )
            prices['OPEN'] = open_prices
            if not open_prices:
                logger.warning(f"No OPEN prices fetched for date range {start_date.date()} to {current_date.date()}")
                logger.warning(f"  (OPEN token ID: {self.OPEN_ID} - verify this is correct)")
        except Exception as e:
            logger.warning(f"Failed to fetch OPEN prices: {e}")
            prices['OPEN'] = {}
        
        return prices
    
    def calculate_benchmark_return(
        self,
        benchmark_prices: Dict[str, float],
        start_date: datetime,
        current_date: datetime,
        weights: Dict[str, float]
    ) -> Optional[float]:
        """Calculate benchmark return from start to current date.
        
        Args:
            benchmark_prices: Dict of {symbol: {date_str: price}} for all tokens
            start_date: Start date of backtest
            current_date: Current date
            weights: Dict of {symbol: weight} for allocation (should sum to 1.0)
        
        Returns:
            Total return percentage, or None if prices unavailable
        """
        start_date_str = start_date.strftime('%Y-%m-%d')
        current_date_str = current_date.strftime('%Y-%m-%d')
        
        # If same day, return 0% (no change)
        if start_date_str == current_date_str:
            return 0.0
        
        # Get start prices
        start_prices = {}
        for symbol, weight in weights.items():
            if symbol not in benchmark_prices:
                logger.warning(f"Symbol {symbol} not in benchmark_prices")
                return None
            
            symbol_prices = benchmark_prices[symbol]
            if not symbol_prices:
                logger.warning(f"No prices available for {symbol}")
                return None
            
            # Try exact date, then nearby dates
            start_price = None
            if start_date_str in symbol_prices:
                start_price = symbol_prices[start_date_str]
            else:
                # Try previous days (up to 7 days back)
                for days_back in range(1, 8):
                    prev_date = start_date - timedelta(days=days_back)
                    prev_date_str = prev_date.strftime('%Y-%m-%d')
                    if prev_date_str in symbol_prices:
                        start_price = symbol_prices[prev_date_str]
                        logger.debug(f"Using {prev_date_str} price for {symbol} start (requested {start_date_str})")
                        break
            
            if start_price is None:
                logger.warning(f"Could not find start price for {symbol} on or before {start_date_str}")
                return None
            
            start_prices[symbol] = start_price
        
        # Get current prices
        current_prices = {}
        for symbol, weight in weights.items():
            symbol_prices = benchmark_prices[symbol]
            
            # Try exact date, then nearby dates
            current_price = None
            if current_date_str in symbol_prices:
                current_price = symbol_prices[current_date_str]
            else:
                # Try previous days (up to 7 days back)
                for days_back in range(1, 8):
                    prev_date = current_date - timedelta(days=days_back)
                    prev_date_str = prev_date.strftime('%Y-%m-%d')
                    if prev_date_str in symbol_prices:
                        current_price = symbol_prices[prev_date_str]
                        logger.debug(f"Using {prev_date_str} price for {symbol} current (requested {current_date_str})")
                        break
            
            if current_price is None:
                logger.warning(f"Could not find current price for {symbol} on or before {current_date_str}")
                return None
            
            current_prices[symbol] = current_price
        
        # Calculate weighted return
        total_return = 0.0
        for symbol, weight in weights.items():
            start_price = start_prices[symbol]
            current_price = current_prices[symbol]
            
            if start_price > 0:
                symbol_return = ((current_price - start_price) / start_price) * 100
                total_return += weight * symbol_return
        
        return total_return
    
    def calculate_all_benchmarks(
        self,
        start_date: datetime,
        current_date: datetime,
        initial_capital: float
    ) -> Dict[str, Optional[float]]:
        """Calculate returns for all benchmark portfolios.
        
        Returns:
            Dict with keys:
            - 'BTC': Return for 100% BTC portfolio
            - 'BTC_ETH': Return for 50/50 BTC/ETH portfolio
            - 'BTC_ETH_OPEN': Return for equal-weight BTC/ETH/OPEN portfolio
        """
        # Fetch all benchmark prices
        benchmark_prices = self.get_benchmark_prices(start_date, current_date)
        
        # Debug: Check if we have any prices
        for symbol, price_dict in benchmark_prices.items():
            if price_dict:
                logger.debug(f"{symbol} has {len(price_dict)} price points")
            else:
                logger.warning(f"{symbol} has no price points")
        
        results = {}
        
        # BTC only (100%)
        btc_return = self.calculate_benchmark_return(
            benchmark_prices,
            start_date,
            current_date,
            {'BTC': 1.0}
        )
        results['BTC'] = btc_return
        if btc_return is None:
            logger.warning("Could not calculate BTC benchmark return")
        
        # BTC + ETH (50/50)
        btc_eth_return = self.calculate_benchmark_return(
            benchmark_prices,
            start_date,
            current_date,
            {'BTC': 0.5, 'ETH': 0.5}
        )
        results['BTC_ETH'] = btc_eth_return
        if btc_eth_return is None:
            logger.warning("Could not calculate BTC+ETH benchmark return")
        
        # BTC + ETH + OPEN (33.3% each)
        btc_eth_open_return = self.calculate_benchmark_return(
            benchmark_prices,
            start_date,
            current_date,
            {'BTC': 1.0/3, 'ETH': 1.0/3, 'OPEN': 1.0/3}
        )
        results['BTC_ETH_OPEN'] = btc_eth_open_return
        if btc_eth_open_return is None:
            logger.warning("Could not calculate BTC+ETH+OPEN benchmark return")
        
        return results

