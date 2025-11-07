"""Generate markdown report from backtest results."""

from datetime import datetime
from pathlib import Path
from typing import List

from .metrics import MetricsCalculator
from .portfolio import Portfolio, Trade
from .signal_parser import Signal


class ReportGenerator:
    """Generate markdown reports from backtest results."""
    
    def __init__(
        self,
        portfolio: Portfolio,
        metrics: MetricsCalculator,
        signals: List[Signal],
        initial_capital: float,
        start_date: datetime,
        end_date: datetime
    ):
        """Initialize report generator."""
        self.portfolio = portfolio
        self.metrics = metrics
        self.signals = signals
        self.initial_capital = initial_capital
        self.start_date = start_date
        self.end_date = end_date
    
    def generate_report(self, output_dir: Path) -> Path:
        """Generate and save the markdown report."""
        report_lines = []
        
        # Header
        report_lines.append("# Backtest Results - Trading Signals")
        report_lines.append("")
        report_lines.append(f"**Date Range:** {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        report_lines.append(f"**Initial Capital:** ${self.initial_capital:,.2f}")
        report_lines.append(f"**Total Signals:** {len(self.signals)}")
        report_lines.append("")
        
        # Summary Metrics
        report_lines.append("## Summary Metrics")
        report_lines.append("")
        
        if self.portfolio.daily_values:
            final_value = self.portfolio.daily_values[-1][1]
            report_lines.append(f"- **Final Value:** ${final_value:,.2f}")
        
        total_return = self.metrics.total_return()
        report_lines.append(f"- **Total Return:** {total_return:+.2f}%")
        
        total_trades = self.metrics.total_trades()
        report_lines.append(f"- **Total Trades:** {total_trades}")
        
        total_pnl = self.metrics.total_pnl()
        report_lines.append(f"- **Total P&L:** ${total_pnl:+,.2f}")
        
        avg_pnl = self.metrics.average_trade_pnl()
        if avg_pnl is not None:
            report_lines.append(f"- **Average P&L per Trade:** ${avg_pnl:+,.2f}")
        
        win_rate = self.metrics.win_rate()
        if win_rate is not None:
            report_lines.append(f"- **Win Rate:** {win_rate:.1f}%")
        
        sharpe = self.metrics.sharpe_ratio()
        if sharpe is not None:
            report_lines.append(f"- **Sharpe Ratio:** {sharpe:.2f}")
        
        max_dd = self.metrics.max_drawdown()
        if max_dd:
            dd_pct, dd_start, dd_end = max_dd
            report_lines.append(f"- **Max Drawdown:** {dd_pct:.2f}%")
            if dd_start and dd_end:
                report_lines.append(f"  - Drawdown Period: {dd_start.strftime('%Y-%m-%d')} to {dd_end.strftime('%Y-%m-%d')}")
        
        report_lines.append("")
        
        # Best/Worst Trades
        report_lines.append("## Best & Worst Trades")
        report_lines.append("")
        
        best_trade = self.metrics.best_trade()
        if best_trade:
            report_lines.append("### Best Trade")
            report_lines.append(f"- **Date:** {best_trade.date.strftime('%Y-%m-%d')}")
            report_lines.append(f"- **Symbol:** {best_trade.symbol} ({best_trade.token_name})")
            report_lines.append(f"- **Action:** {best_trade.action}")
            report_lines.append(f"- **Quantity:** {best_trade.quantity:.4f}")
            report_lines.append(f"- **Price:** ${best_trade.price:.2f}")
            if best_trade.entry_price:
                report_lines.append(f"- **Entry Price:** ${best_trade.entry_price:.2f}")
            report_lines.append(f"- **P&L:** ${best_trade.pnl:+,.2f}")
            report_lines.append("")
        
        worst_trade = self.metrics.worst_trade()
        if worst_trade:
            report_lines.append("### Worst Trade")
            report_lines.append(f"- **Date:** {worst_trade.date.strftime('%Y-%m-%d')}")
            report_lines.append(f"- **Symbol:** {worst_trade.symbol} ({worst_trade.token_name})")
            report_lines.append(f"- **Action:** {worst_trade.action}")
            report_lines.append(f"- **Quantity:** {worst_trade.quantity:.4f}")
            report_lines.append(f"- **Price:** ${worst_trade.price:.2f}")
            if worst_trade.entry_price:
                report_lines.append(f"- **Entry Price:** ${worst_trade.entry_price:.2f}")
            report_lines.append(f"- **P&L:** ${worst_trade.pnl:+,.2f}")
            report_lines.append("")
        
        # Token Performance
        report_lines.append("## Token Performance")
        report_lines.append("")
        
        token_perf = self.metrics.token_performance()
        if token_perf:
            report_lines.append("| Token | Trades | Total P&L | Total Volume |")
            report_lines.append("|-------|--------|-----------|-------------|")
            
            for symbol, stats in sorted(token_perf.items(), key=lambda x: x[1]['total_pnl'], reverse=True):
                report_lines.append(
                    f"| {symbol} | {stats['trades']} | ${stats['total_pnl']:+,.2f} | ${stats['total_volume']:,.2f} |"
                )
            report_lines.append("")
        
        # Daily Portfolio Value
        report_lines.append("## Daily Portfolio Value")
        report_lines.append("")
        report_lines.append("| Date | Portfolio Value | Cash | Positions Value |")
        report_lines.append("|------|----------------|------|-----------------|")
        
        for date, total_value in self.portfolio.daily_values:
            # Calculate cash and positions value
            # Get prices for all tokens on this date
            # For simplicity, we'll just show total value
            cash = self.portfolio.cash
            positions_value = total_value - cash
            
            report_lines.append(
                f"| {date.strftime('%Y-%m-%d')} | ${total_value:,.2f} | ${cash:,.2f} | ${positions_value:,.2f} |"
            )
        report_lines.append("")
        
        # Trade Log
        report_lines.append("## Trade Log")
        report_lines.append("")
        report_lines.append("| Date | Action | Symbol | Quantity | Price | Value | P&L | Signal |")
        report_lines.append("|------|--------|--------|----------|-------|-------|-----|--------|")
        
        for trade in self.portfolio.trades:
            pnl_str = f"${trade.pnl:+,.2f}" if trade.pnl is not None else "-"
            report_lines.append(
                f"| {trade.date.strftime('%Y-%m-%d')} | {trade.action} | {trade.symbol} | "
                f"{trade.quantity:.4f} | ${trade.price:.2f} | ${trade.value:,.2f} | "
                f"{pnl_str} | {trade.signal_type} |"
            )
        report_lines.append("")
        
        # Signals Processed
        report_lines.append("## Signals Processed")
        report_lines.append("")
        report_lines.append("| Date | Symbol | Token Name | Signal | Reason |")
        report_lines.append("|------|--------|------------|--------|--------|")
        
        for signal in self.signals:
            # Truncate reason if too long
            reason = signal.reason[:80] + "..." if len(signal.reason) > 80 else signal.reason
            report_lines.append(
                f"| {signal.date.strftime('%Y-%m-%d')} | {signal.symbol} | {signal.token_name} | "
                f"{signal.signal_type} | {reason} |"
            )
        report_lines.append("")
        
        # Footer
        report_lines.append("---")
        report_lines.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
        # Write to file
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        filename = output_dir / f"backtest_results_{self.start_date.strftime('%Y-%m-%d')}_to_{self.end_date.strftime('%Y-%m-%d')}.md"
        
        with open(filename, 'w') as f:
            f.write('\n'.join(report_lines))
        
        return filename


