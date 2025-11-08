"""Incremental backtest runner for daily signal processing."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .benchmarks import BenchmarkCalculator
from .portfolio import Portfolio
from .portfolio_persistence import PortfolioPersistence
from .price_fetcher import PriceFetcher
from .signal_parser import Signal, SignalParser

logger = logging.getLogger(__name__)


class IncrementalBacktest:
    """Run incremental backtest for a single day."""
    
    def __init__(
        self,
        state_file: Path,
        writeup_dir: Path,
        initial_capital: float,
        price_fetcher: Optional[PriceFetcher] = None
    ):
        """Initialize incremental backtest.
        
        Args:
            state_file: Path to portfolio state JSON file
            writeup_dir: Directory containing signals markdown files
            initial_capital: Initial capital for new portfolios
            price_fetcher: Optional PriceFetcher instance (creates new if None)
        """
        self.persistence = PortfolioPersistence(state_file)
        self.writeup_dir = Path(writeup_dir)
        self.initial_capital = initial_capital
        self.price_fetcher = price_fetcher or PriceFetcher()
        self.benchmark_calc = BenchmarkCalculator(self.price_fetcher)
    
    def run(self, current_date: datetime, signals: List[Signal]) -> Optional[Dict]:
        """Run incremental backtest for current date.
        
        Args:
            current_date: Date to process (typically today)
            signals: List of signals for current_date
        
        Returns:
            Dict with backtest results, or None if error
        """
        try:
            # Load or initialize portfolio
            state = self.persistence.load()
            
            if state is None:
                # First run - initialize new portfolio
                logger.info("Initializing new portfolio (first run)")
                portfolio = Portfolio(cash=self.initial_capital)
                start_date = current_date
            else:
                # Load existing portfolio
                logger.info("Loading existing portfolio state")
                portfolio, start_date, initial_capital = self.persistence.create_portfolio_from_state(state)
            
            # Get current prices for all tokens we need
            # First, get all symbols from signals and existing positions
            all_symbols = set()
            for signal in signals:
                all_symbols.add(signal.symbol)
            for symbol in portfolio.positions.keys():
                all_symbols.add(symbol)
            
            # Fetch prices for all symbols
            current_prices = {}
            for symbol in all_symbols:
                coingecko_id = self.price_fetcher.get_coingecko_id(symbol)
                if coingecko_id:
                    # Fetch price for current date
                    price = self.price_fetcher.get_price(symbol, current_date)
                    if price is not None:
                        current_prices[symbol] = price
                    else:
                        logger.warning(f"Could not fetch price for {symbol} on {current_date.strftime('%Y-%m-%d')}")
                else:
                    logger.warning(f"Could not find CoinGecko ID for {symbol}")
            
            # Process signals for today
            trades_today = []
            for signal in signals:
                price = current_prices.get(signal.symbol)
                trades = portfolio.process_signal(signal, price, current_prices)
                trades_today.extend(trades)
            
            # Record daily portfolio value
            portfolio.record_daily_value(current_date, current_prices)
            
            # Calculate current portfolio value
            portfolio_value = portfolio.get_total_value(current_prices)
            total_return = ((portfolio_value - self.initial_capital) / self.initial_capital) * 100
            
            # Calculate benchmark returns
            # Only calculate if current_date is on or after start_date
            if current_date >= start_date:
                benchmark_returns = self.benchmark_calc.calculate_all_benchmarks(
                    start_date,
                    current_date,
                    self.initial_capital
                )
            else:
                logger.warning(f"Cannot calculate benchmarks: current_date ({current_date.date()}) is before start_date ({start_date.date()})")
                benchmark_returns = {'BTC': None, 'BTC_ETH': None, 'BTC_ETH_OPEN': None}
            
            # Calculate days since start
            days_since_start = (current_date - start_date).days
            
            # Save updated portfolio state
            self.persistence.save(portfolio, start_date, self.initial_capital)
            
            # Prepare results
            results = {
                'portfolio_value': portfolio_value,
                'total_return': total_return,
                'initial_capital': self.initial_capital,
                'start_date': start_date,
                'current_date': current_date,
                'days_since_start': days_since_start,
                'positions': [
                    {
                        'symbol': pos.symbol,
                        'token_name': pos.token_name,
                        'quantity': pos.quantity,
                        'entry_price': pos.entry_price,
                        'current_price': current_prices.get(pos.symbol),
                        'current_value': pos.quantity * current_prices.get(pos.symbol, 0),
                        'unrealized_pnl': (current_prices.get(pos.symbol, 0) - pos.entry_price) * pos.quantity if current_prices.get(pos.symbol) else None,
                    }
                    for pos in portfolio.positions.values()
                ],
                'trades_today': [
                    {
                        'action': trade.action,
                        'symbol': trade.symbol,
                        'token_name': trade.token_name,
                        'quantity': trade.quantity,
                        'price': trade.price,
                        'value': trade.value,
                        'pnl': trade.pnl,
                    }
                    for trade in trades_today
                ],
                'benchmark_returns': benchmark_returns,
                'cash': portfolio.cash,
            }
            
            return results
            
        except Exception as e:
            logger.error(f"Error running incremental backtest: {e}", exc_info=True)
            return None
    
    def close(self):
        """Close price fetcher."""
        if self.price_fetcher:
            self.price_fetcher.close()

