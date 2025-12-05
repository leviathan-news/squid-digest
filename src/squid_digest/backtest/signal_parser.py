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
    
    # Pattern to match signal lines in ACTUAL format (after digest.py transformation):
    # 🟡 Bitcoin (<a href="url">$BTC</a>): WEAK BUY - reason text
    # OR the original LLM format (for temp file parsing before transformation):
    # **$LINK ChainLink Token: STRONG BUY** - reason text
    #
    # Handles both emoji-prefixed HTML format and bold markdown format
    # Case-insensitive to handle "Strong Buy", "STRONG BUY", "strong buy", etc.

    # Pattern 1: Emoji + HTML format (final output format)
    # Matches: 🟡 Bitcoin (<a href="...">$BTC</a>): WEAK BUY - reason
    SIGNAL_PATTERN_HTML = re.compile(
        r'[🟢🔴🟡🟠⚪]\s*([^(]+?)\s*\(<a[^>]*>\$([A-Za-z0-9]+)</a>\):\s*([A-Za-z\s]+?)\s*-\s*(.+?)(?:\s*$)',
        re.MULTILINE | re.DOTALL | re.IGNORECASE
    )

    # Pattern 2: Bold markdown format (raw LLM output format)
    # Matches: **$LINK ChainLink Token: STRONG BUY** - reason text
    SIGNAL_PATTERN_BOLD = re.compile(
        r'\*\*\$([A-Za-z0-9]+)\s+([^:]+?):\s+([A-Za-z\s]+?)\*\*\s*-\s*(.+?)(?:\s*\(\[more info\]|$)',
        re.MULTILINE | re.DOTALL | re.IGNORECASE
    )

    # Pattern 3: Emoji + markdown link format (intermediate format)
    # Matches: 🟡 Bitcoin ([$BTC](url)): WEAK BUY - reason
    SIGNAL_PATTERN_MD_LINK = re.compile(
        r'[🟢🔴🟡🟠⚪]\s*([^(]+?)\s*\(\[\$([A-Za-z0-9]+)\]\([^)]+\)\):\s*([A-Za-z\s]+?)\s*-\s*(.+?)(?:\s*$)',
        re.MULTILINE | re.DOTALL | re.IGNORECASE
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
        
        # Try multiple patterns to handle different format variations
        # Pattern 1: Emoji + HTML (final output) - groups: (token_name, symbol, signal_type, reason)
        # Pattern 2: Bold markdown (LLM raw) - groups: (symbol, token_name, signal_type, reason)
        # Pattern 3: Emoji + markdown link - groups: (token_name, symbol, signal_type, reason)

        patterns_to_try = [
            ('html', self.SIGNAL_PATTERN_HTML),      # token_name, symbol, signal, reason
            ('bold', self.SIGNAL_PATTERN_BOLD),      # symbol, token_name, signal, reason
            ('md_link', self.SIGNAL_PATTERN_MD_LINK) # token_name, symbol, signal, reason
        ]

        for pattern_name, pattern in patterns_to_try:
            matches = list(pattern.finditer(signals_content))
            if matches:
                for match in matches:
                    # Extract groups based on pattern type
                    if pattern_name == 'bold':
                        # Bold format: **$SYMBOL Token: SIGNAL** - reason
                        symbol = match.group(1)
                        token_name = match.group(2).strip()
                    else:
                        # HTML and MD link formats: emoji Token ($SYMBOL): SIGNAL - reason
                        token_name = match.group(1).strip()
                        symbol = match.group(2)

                    signal_type_raw = match.group(3).strip()
                    signal_type = signal_type_raw.upper()  # Normalize to uppercase
                    reason = match.group(4).strip()

                    # Clean up reason (remove markdown links and trailing content)
                    reason = re.sub(r'\(\[more info\]\([^)]+\)\)', '', reason).strip()
                    # Remove any trailing HTML or markdown artifacts
                    reason = re.sub(r'\s*<[^>]+>\s*$', '', reason).strip()

                    # Validate signal type (after normalization)
                    if signal_type not in self.VALID_SIGNALS:
                        print(f"Warning: Unknown signal type '{signal_type_raw}' (normalized: '{signal_type}') for {symbol} on {date_str}")
                        continue

                    signals.append(Signal(
                        date=signal_date,
                        symbol=symbol,
                        token_name=token_name,
                        signal_type=signal_type,
                        reason=reason
                    ))

                # If we found signals with this pattern, don't try other patterns
                if signals:
                    break
        
        return signals
    
    def parse_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Signal]:
        """Parse all signal files in a date range.
        
        Searches recursively in Year/Month/Day subdirectories.
        """
        all_signals = []
        
        # Find all signals_*.md files recursively (handles both old flat structure and new YYYY/MM/DD structure)
        signal_files = sorted(self.writeup_dir.rglob('signals_*.md'))
        
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
