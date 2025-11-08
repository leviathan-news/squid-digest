"""Format backtest results for newsletter inclusion."""

from datetime import datetime
from typing import Dict, Optional


def format_backtest_for_newsletter(results: Dict) -> str:
    """Format backtest results as markdown for newsletter.
    
    Args:
        results: Dict from IncrementalBacktest.run()
    
    Returns:
        Formatted markdown string
    """
    lines = []
    
    lines.append("## 📈 Backtest Results")
    lines.append("")
    
    # Summary stats
    portfolio_value = results['portfolio_value']
    total_return = results['total_return']
    initial_capital = results['initial_capital']
    days_since_start = results['days_since_start']
    start_date = results['start_date']
    current_date = results['current_date']
    
    lines.append(f"**Portfolio Value:** ${portfolio_value:,.2f}")
    lines.append(f"**Total Return:** {total_return:+.2f}%")
    lines.append(f"**Days Since Start:** {days_since_start} (since {start_date.strftime('%Y-%m-%d')})")
    lines.append("")
    
    # Current positions
    positions = results['positions']
    if positions:
        lines.append("### Current Positions")
        lines.append("")
        
        for pos in positions:
            symbol = pos['symbol']
            quantity = pos['quantity']
            entry_price = pos['entry_price']
            current_price = pos['current_price']
            current_value = pos['current_value']
            unrealized_pnl = pos['unrealized_pnl']
            
            if current_price is not None:
                price_str = f"${current_price:.2f}"
                value_str = f"${current_value:,.2f}"
                if unrealized_pnl is not None:
                    pnl_str = f" (P&L: ${unrealized_pnl:+,.2f})"
                else:
                    pnl_str = ""
            else:
                price_str = "N/A"
                value_str = "N/A"
                pnl_str = ""
            
            # Format as: **BTC**: 0.0196 @ $101983.74 entry, $101983.74 current = $2,000.00 (P&L: $+0.00)
            lines.append(
                f"- **{symbol}**: {quantity:.4f} @ ${entry_price:.2f} entry, {price_str} current = {value_str}{pnl_str}"
            )
        lines.append("")
    else:
        lines.append("### Current Positions")
        lines.append("")
        lines.append("*No open positions*")
        lines.append("")
    
    # Trades today
    trades_today = results['trades_today']
    if trades_today:
        lines.append("### Trades Today")
        lines.append("")
        for trade in trades_today:
            action = trade['action']
            symbol = trade['symbol']
            quantity = trade['quantity']
            price = trade['price']
            value = trade['value']
            pnl = trade.get('pnl')
            
            if pnl is not None:
                pnl_str = f" (P&L: ${pnl:+,.2f})"
            else:
                pnl_str = ""
            
            lines.append(f"- **{action}** {quantity:.4f} {symbol} @ ${price:.2f} (${value:,.2f}){pnl_str}")
        lines.append("")
    else:
        lines.append("### Trades Today")
        lines.append("")
        lines.append("*No trades executed today*")
        lines.append("")
    
    # Benchmark comparison
    lines.append("### Performance vs Benchmarks")
    lines.append("")
    benchmark_returns = results['benchmark_returns']
    
    portfolio_return = total_return
    
    # BTC only
    btc_return = benchmark_returns.get('BTC')
    if btc_return is not None:
        diff = portfolio_return - btc_return
        lines.append(f"- **BTC Only:** {btc_return:+.2f}% (Portfolio: {diff:+.2f}%)")
    else:
        lines.append("- **BTC Only:** N/A")
    
    # BTC + ETH
    btc_eth_return = benchmark_returns.get('BTC_ETH')
    if btc_eth_return is not None:
        diff = portfolio_return - btc_eth_return
        lines.append(f"- **BTC + ETH (50/50):** {btc_eth_return:+.2f}% (Portfolio: {diff:+.2f}%)")
    else:
        lines.append("- **BTC + ETH (50/50):** N/A")
    
    # BTC + ETH + OPEN
    btc_eth_open_return = benchmark_returns.get('BTC_ETH_OPEN')
    if btc_eth_open_return is not None:
        diff = portfolio_return - btc_eth_open_return
        lines.append(f"- **BTC + ETH + OPEN (33.3% each):** {btc_eth_open_return:+.2f}% (Portfolio: {diff:+.2f}%)")
    else:
        lines.append("- **BTC + ETH + OPEN (33.3% each):** N/A")
    
    lines.append("")
    lines.append(f"*Cash: ${results['cash']:,.2f}*")
    lines.append("")
    
    return "\n".join(lines)


