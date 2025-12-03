"""Format backtest results for newsletter inclusion."""

from datetime import datetime
from typing import Dict, Optional


def format_backtest_for_newsletter(buy_results: Dict, sell_results: Optional[Dict] = None) -> str:
    """Format backtest results as markdown for newsletter.

    Args:
        buy_results: Dict from IncrementalBacktest.run() for buy_the_news strategy
        sell_results: Optional dict from IncrementalBacktest.run() for sell_the_news strategy

    Returns:
        Formatted markdown string
    """
    lines = []

    lines.append("## 📈 Backtest Results")

    # If we have both strategies, show them side-by-side
    if sell_results is not None:
        lines.append("### Buy the News Strategy")
        lines.append("")
        lines.append("*How would a portfolio perform if it traded daily on Leviathan News headlines?*")
        lines.append("")
        lines.append("*Strategy includes risk management: -20% stop loss on all positions, +20% profit-taking (50% position reduction) on all positions.*")
        lines.append("")
        _format_strategy_results(lines, buy_results)
        lines.append("### Sell the News Strategy")
        lines.append("")
        lines.append("*Once it's in the headlines, it's supposedly too late! How would your portfolio perform if you did the opposite of the signal?*")
        lines.append("")
        lines.append("*Strategy includes risk management: -20% stop loss on all positions, +20% profit-taking (50% position reduction) on all positions.*")
        lines.append("")
        _format_strategy_results(lines, sell_results)
    else:
        # Single strategy (backward compatibility)
        lines.append("*Strategy includes risk management: -20% stop loss on all positions, +20% profit-taking (50% position reduction) on all positions.*")
        lines.append("")
        _format_strategy_results(lines, buy_results)
    
    # Benchmark comparison (show once, using buy strategy's benchmarks)
    lines.append("### Performance vs Benchmarks")
    lines.append("")
    lines.append("*Benchmark returns show the benchmark's performance since portfolio start. Portfolio returns show how much better/worse the portfolio performed relative to the benchmark.*")
    lines.append("")
    
    # Use buy_results for benchmarks (they should be the same for both strategies)
    benchmark_returns = buy_results['benchmark_returns']
    buy_return = buy_results['total_return']
    
    # Show both strategies' performance vs benchmarks
    if sell_results is not None:
        sell_return = sell_results['total_return']
        
        # BTC only
        btc_return = benchmark_returns.get('BTC')
        if btc_return is not None:
            buy_diff = buy_return - btc_return
            sell_diff = sell_return - btc_return
            lines.append(f"- **BTC Only:** {btc_return:+.2f}%")
            lines.append(f"  * Buy: {buy_diff:+.2f}%")
            lines.append(f"  * Sell: {sell_diff:+.2f}%")
        else:
            lines.append("- **BTC Only:** N/A")
        
        # BTC + ETH
        btc_eth_return = benchmark_returns.get('BTC_ETH')
        if btc_eth_return is not None:
            buy_diff = buy_return - btc_eth_return
            sell_diff = sell_return - btc_eth_return
            lines.append(f"- **BTC + ETH (50/50):** {btc_eth_return:+.2f}%")
            lines.append(f"  * Buy: {buy_diff:+.2f}%")
            lines.append(f"  * Sell: {sell_diff:+.2f}%")
        else:
            lines.append("- **BTC + ETH (50/50):** N/A")
        
        # BTC + ETH + OPEN
        btc_eth_open_return = benchmark_returns.get('BTC_ETH_OPEN')
        if btc_eth_open_return is not None:
            buy_diff = buy_return - btc_eth_open_return
            sell_diff = sell_return - btc_eth_open_return
            lines.append(f"- **BTC + ETH + OPEN (33/33/33):** {btc_eth_open_return:+.2f}%")
            lines.append(f"  * Buy: {buy_diff:+.2f}%")
            lines.append(f"  * Sell: {sell_diff:+.2f}%")
        else:
            lines.append("- **BTC + ETH + OPEN (33/33/33):** N/A")
    else:
        # Single strategy
        portfolio_return = buy_return
        
        # BTC only
        btc_return = benchmark_returns.get('BTC')
        if btc_return is not None:
            diff = portfolio_return - btc_return
            lines.append(f"- **BTC Only:** {btc_return:+.2f}%")
            lines.append(f"  * Portfolio: {diff:+.2f}%")
        else:
            lines.append("- **BTC Only:** N/A")
        
        # BTC + ETH
        btc_eth_return = benchmark_returns.get('BTC_ETH')
        if btc_eth_return is not None:
            diff = portfolio_return - btc_eth_return
            lines.append(f"- **BTC + ETH (50/50):** {btc_eth_return:+.2f}%")
            lines.append(f"  * Portfolio: {diff:+.2f}%")
        else:
            lines.append("- **BTC + ETH (50/50):** N/A")
        
        # BTC + ETH + OPEN
        btc_eth_open_return = benchmark_returns.get('BTC_ETH_OPEN')
        if btc_eth_open_return is not None:
            diff = portfolio_return - btc_eth_open_return
            lines.append(f"- **BTC + ETH + OPEN (33/33/33):** {btc_eth_open_return:+.2f}%")
            lines.append(f"  * Portfolio: {diff:+.2f}%")
        else:
            lines.append("- **BTC + ETH + OPEN (33/33/33):** N/A")

    return "\n".join(lines)


def _format_strategy_results(lines: list, results: Dict) -> None:
    """Format results for a single strategy."""
    # Summary stats
    portfolio_value = results['portfolio_value']
    total_return = results['total_return']
    initial_capital = results['initial_capital']
    days_since_start = results['days_since_start']
    start_date = results['start_date']
    current_date = results['current_date']
    
    # Use backticks for dollar amounts to prevent GitHub math rendering
    lines.append(f"- **Portfolio Value:** `${portfolio_value:,.2f}`")
    lines.append(f"- **Total Return:** {total_return:+.2f}%")
    lines.append(f"- **Days Since Start:** {days_since_start} (since {start_date.strftime('%Y-%m-%d')})")
    lines.append(f"- **Cash:** `${results['cash']:,.2f}`")
    lines.append("")
    
    # Current positions
    positions = results['positions']
    if positions:
        lines.append("#### Current Positions")
        lines.append("")
        
        for pos in positions:
            symbol = pos['symbol']
            quantity = pos['quantity']
            entry_price = pos['entry_price']
            current_price = pos['current_price']
            current_value = pos['current_value']
            unrealized_pnl = pos['unrealized_pnl']
            
            # Determine if this is a short position
            is_short = quantity < 0
            position_emoji = "🔴" if is_short else "🟢"
            
            if current_price is not None:
                # Format current price with commas for BTC/ETH (prices >= 1000)
                # Use backticks for dollar amounts to prevent GitHub from treating them as math
                price_str = f"`${current_price:,.2f}`" if current_price >= 1000 else f"`${current_price:.2f}`"
                value_str = f"`${current_value:,.2f}`"
                if unrealized_pnl is not None:
                    # Use backticks for P/L dollar amount to prevent math rendering
                    pnl_str = f" (P/L: `${unrealized_pnl:+,.2f}`)"
                else:
                    pnl_str = ""
            else:
                price_str = "N/A"
                value_str = "N/A"
                pnl_str = ""
            
            # Format as: 🟢 **BTC**: 0.0196 @ $101,983.74 entry, $101,983.74 current = $2,000.00 (P/L: $+0.00)
            # For shorts: 🔴 **BTC**: -0.0196 (SHORT) @ $101,983.74 entry, ...
            # Format large quantities with commas (e.g., 1,176.56985)
            def format_quantity(qty):
                # Split into integer and decimal parts
                parts = f"{abs(qty):.5f}".split(".")
                integer_part = int(parts[0]) if parts[0] else 0
                decimal_part = parts[1] if len(parts) > 1 else "00000"
                return f"{integer_part:,}.{decimal_part}"
            
            if is_short:
                quantity_str = f"{format_quantity(quantity)} (SHORT)"
            else:
                quantity_str = format_quantity(quantity)
            # Format entry price with commas for BTC/ETH (use backticks to prevent math rendering)
            entry_price_str = f"`${entry_price:,.2f}`" if entry_price >= 1000 else f"`${entry_price:.2f}`"
            lines.append(
                f"- {position_emoji} **{symbol}**: {quantity_str} @ {entry_price_str} entry, {price_str} current = {value_str}{pnl_str}"
            )
        lines.append("")
    else:
        lines.append("#### Current Positions")
        lines.append("")
        lines.append("*No open positions*")
        lines.append("")
    
    # Trades today
    trades_today = results['trades_today']
    if trades_today:
        lines.append("#### Trades Today")
        lines.append("")
        for trade in trades_today:
            action = trade['action']
            symbol = trade['symbol']
            quantity = trade['quantity']
            price = trade['price']
            value = trade['value']
            pnl = trade.get('pnl')
            
            # Determine emoji based on action
            trade_emoji = "🔴" if action == "SHORT" else "🟢"
            
            # Format price with commas for BTC/ETH (prices > 1000)
            # Use backticks for dollar amounts to prevent GitHub from treating them as math
            price_str = f"`${price:,.2f}`" if price >= 1000 else f"`${price:.2f}`"
            value_str = f"`${value:,.2f}`"
            
            # Format value and P/L together to avoid double parentheses
            if pnl is not None:
                # Combine value and P/L in single parenthetical: ($991.17, P/L: $+32.01)
                # Use backticks for P/L dollar amount to prevent math rendering
                value_pnl_str = f"({value_str}, P/L: `${pnl:+,.2f}`)"
            else:
                # Just show value when no P/L
                value_pnl_str = f"({value_str})"
            
            lines.append(f"- {trade_emoji} **{action}** {quantity:.4f} {symbol} @ {price_str} {value_pnl_str}")
        lines.append("")
    else:
        lines.append("#### Trades Today")
        lines.append("")
        lines.append("*No trades executed today*")
        lines.append("")
    
    # Benchmark comparison (only show once, using buy strategy's benchmarks)
    # This will be handled in the main function


