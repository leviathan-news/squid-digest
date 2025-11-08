"""Parse trading signals from markdown files."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class Signal:
    """Represents a single trading signal."""
    date: datetime
    symbol: str  # e.g., "LINK", "BTC"
    token_name: str  # e.g., "ChainLink Token"
    signal_type: str  # e.g., "STRONG BUY", "WEAK SELL"
    reason: str  # The reasoning text after the dash
    

class SignalParser:
    """Parse trading signals from markdown signal files."""
    
    # Pattern to match signal lines like:
    # **$LINK ChainLink Token: STRONG BUY** - reason text
    # Handles tokens with parentheses and special chars in name
    # Symbol can have lowercase (e.g., fxUSD)
    SIGNAL_PATTERN = re.compile(
        r'\*\*\$([A-Za-z0-9]+)\s+([^:]+?):\s+([A-Z\s]+)\*\*\s*-\s*(.+?)(?:\s*\(\[more info\]|$)',
        re.MULTILINE | re.DOTALL
    )
    
    # Signal types we recognize
    VALID_SIGNALS = {
        'STRONG BUY', 'BUY', 'WEAK BUY',
        'WEAK SELL', 'SELL', 'STRONG SELL'
    }
    
    def __init__(self, writeup_dir: Path):
        """Initialize parser with writeup directory."""
        self.writeup_dir = Path(writeup_dir)
    
    def parse_file(self, filepath: Path) -> List[Signal]:
        """Parse a single signals markdown file."""
        signals = []
        
        # Extract date from filename: signals_2025-10-17.md or digest_2025-10-17.md -> 2025-10-17
        # Try signals_ prefix first, then any prefix with date pattern
        match = re.search(r'signals_(\d{4}-\d{2}-\d{2})\.md', filepath.name)
        if not match:
            # Try any prefix with date pattern (e.g., digest_2025-10-17.md)
            match = re.search(r'_(\d{4}-\d{2}-\d{2})\.md', filepath.name)
        
        if not match:
            return signals
        
        date_str = match.group(1)
        signal_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Warning: Could not read {filepath}: {e}")
            return signals
        
        # Find the Trading Signals section
        signals_section_start = content.find('## 🎯 Trading Signals')
        if signals_section_start == -1:
            return signals
        
        signals_content = content[signals_section_start:]
        
        # Find all signal matches
        for match in self.SIGNAL_PATTERN.finditer(signals_content):
            symbol = match.group(1)
            token_name = match.group(2).strip()
            signal_type = match.group(3).strip()
            reason = match.group(4).strip()
            
            # Clean up reason (remove markdown links)
            reason = re.sub(r'\(\[more info\]\([^)]+\)\)', '', reason).strip()
            
            # Validate signal type
            if signal_type not in self.VALID_SIGNALS:
                print(f"Warning: Unknown signal type '{signal_type}' for {symbol} on {date_str}")
                continue
            
            signals.append(Signal(
                date=signal_date,
                symbol=symbol,
                token_name=token_name,
                signal_type=signal_type,
                reason=reason
            ))
        
        return signals
    
    def parse_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Signal]:
        """Parse all signal files in a date range."""
        all_signals = []
        
        # Find all signals_*.md files
        pattern = self.writeup_dir / 'signals_*.md'
        signal_files = sorted(pattern.parent.glob(pattern.name))
        
        for filepath in signal_files:
            # Extract date from filename
            match = re.search(r'signals_(\d{4}-\d{2}-\d{2})\.md', filepath.name)
            if not match:
                continue
            
            file_date = datetime.strptime(match.group(1), '%Y-%m-%d')
            
            # Check if file is in date range
            if start_date <= file_date <= end_date:
                signals = self.parse_file(filepath)
                all_signals.extend(signals)
                print(f"Parsed {len(signals)} signals from {filepath.name}")
        
        return sorted(all_signals, key=lambda s: (s.date, s.symbol))
