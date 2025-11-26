"""Calculate performance metrics for backtest results."""

import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .portfolio import Portfolio, Trade


class MetricsCalculator:
    """Calculate various performance metrics."""
    
    def __init__(self, portfolio: Portfolio, initial_capital: float):
        """Initialize metrics calculator."""
        self.portfolio = portfolio
        self.initial_capital = initial_capital
    
    def total_return(self) -> float:
        """Calculate total return percentage."""
        if not self.portfolio.daily_values:
            return 0.0
        
        final_value = self.portfolio.daily_values[-1][1]
        return ((final_value - self.initial_capital) / self.initial_capital) * 100
    
    def sharpe_ratio(self, risk_free_rate: float = 0.0) -> Optional[float]:
        """Calculate Sharpe ratio."""
        if len(self.portfolio.daily_values) < 2:
            return None
        
        # Calculate daily returns
        returns = []
        prev_value = self.initial_capital
        
        for date, value in self.portfolio.daily_values:
            daily_return = (value - prev_value) / prev_value if prev_value > 0 else 0.0
            returns.append(daily_return)
            prev_value = value
        
        if not returns:
            return None
        
        # Calculate mean and std dev
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return None
        
        # Annualize (assuming daily returns)
        annualized_return = mean_return * 365
        annualized_std = std_dev * math.sqrt(365)
        
        sharpe = (annualized_return - risk_free_rate) / annualized_std
        return sharpe
    
    def win_rate(self) -> Optional[float]:
        """Calculate win rate (percentage of profitable trades)."""
        sell_trades = [t for t in self.portfolio.trades if t.action == 'SELL' and t.pnl is not None]
        
        if not sell_trades:
            return None
        
        profitable = sum(1 for t in sell_trades if t.pnl > 0)
        return (profitable / len(sell_trades)) * 100
    
    def total_trades(self) -> int:
        """Get total number of trades."""
        return len(self.portfolio.trades)
    
    def total_pnl(self) -> float:
        """Calculate total P&L from closed positions."""
        sell_trades = [t for t in self.portfolio.trades if t.pnl is not None]
        return sum(t.pnl for t in sell_trades)
    
    def best_trade(self) -> Optional[Trade]:
        """Get the best (most profitable) trade."""
        sell_trades = [t for t in self.portfolio.trades if t.pnl is not None]
        if not sell_trades:
            return None
        return max(sell_trades, key=lambda t: t.pnl)
    
    def worst_trade(self) -> Optional[Trade]:
        """Get the worst (least profitable) trade."""
        sell_trades = [t for t in self.portfolio.trades if t.pnl is not None]
        if not sell_trades:
            return None
        return min(sell_trades, key=lambda t: t.pnl)
    
    def average_trade_pnl(self) -> Optional[float]:
        """Calculate average P&L per trade."""
        sell_trades = [t for t in self.portfolio.trades if t.pnl is not None]
        if not sell_trades:
            return None
        return sum(t.pnl for t in sell_trades) / len(sell_trades)
    
    def token_performance(self) -> Dict[str, Dict[str, float]]:
        """Calculate performance metrics per token."""
        token_stats: Dict[str, Dict[str, float]] = {}
        
        for trade in self.portfolio.trades:
            symbol = trade.symbol
            
            if symbol not in token_stats:
                token_stats[symbol] = {
                    'total_pnl': 0.0,
                    'trades': 0,
                    'buy_count': 0,
                    'sell_count': 0,
                    'total_volume': 0.0
                }
            
            stats = token_stats[symbol]
            stats['trades'] += 1
            stats['total_volume'] += trade.value
            
            if trade.action == 'BUY':
                stats['buy_count'] += 1
            elif trade.action == 'SELL':
                stats['sell_count'] += 1
                if trade.pnl is not None:
                    stats['total_pnl'] += trade.pnl
        
        return token_stats
    
    def max_drawdown(self) -> Optional[Tuple[float, datetime, datetime]]:
        """Calculate maximum drawdown."""
        if len(self.portfolio.daily_values) < 2:
            return None
        
        peak = self.initial_capital
        max_dd = 0.0
        peak_date = None
        dd_start_date = None
        dd_end_date = None
        
        for date, value in self.portfolio.daily_values:
            if value > peak:
                peak = value
                peak_date = date
                dd_start_date = None
            else:
                drawdown = (peak - value) / peak if peak > 0 else 0.0
                if drawdown > max_dd:
                    max_dd = drawdown
                    if peak_date:
                        dd_start_date = peak_date
                    dd_end_date = date
        
        return (max_dd * 100, dd_start_date, dd_end_date) if max_dd > 0 else None
    
    def compare_to_benchmark(
        self,
        benchmark_prices: List[Tuple[datetime, float]]
    ) -> Optional[Dict[str, float]]:
        """Compare portfolio performance to a benchmark (e.g., BTC, ETH)."""
        if not self.portfolio.daily_values or not benchmark_prices:
            return None
        
        # Align dates
        portfolio_dict = {date: value for date, value in self.portfolio.daily_values}
        benchmark_dict = {date: price for date, price in benchmark_prices}
        
        common_dates = sorted(set(portfolio_dict.keys()) & set(benchmark_dict.keys()))
        
        if len(common_dates) < 2:
            return None
        
        # Calculate returns
        portfolio_start = portfolio_dict[common_dates[0]]
        portfolio_end = portfolio_dict[common_dates[-1]]
        portfolio_return = ((portfolio_end - portfolio_start) / portfolio_start) * 100
        
        benchmark_start = benchmark_dict[common_dates[0]]
        benchmark_end = benchmark_dict[common_dates[-1]]
        benchmark_return = ((benchmark_end - benchmark_start) / benchmark_start) * 100
        
        return {
            'portfolio_return': portfolio_return,
            'benchmark_return': benchmark_return,
            'excess_return': portfolio_return - benchmark_return
        }
