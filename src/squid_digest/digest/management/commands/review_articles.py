"""
Django management command to review recent articles for tickers and validate readiness.

This command:
1. Lists recent signals/digest files
2. Extracts tickers from each article
3. Validates completeness (signals, backtest results, etc.)
4. Reports readiness status for each article
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

from django.core.management.base import BaseCommand
from squid_digest.backtest.signal_parser import SignalParser, Signal
from squid_digest.config import WRITEUP_DIR


class ArticleReviewer:
    """Review articles for tickers and validate readiness."""
    
    def __init__(self, writeup_dir: Path):
        self.writeup_dir = Path(writeup_dir)
        self.signal_parser = SignalParser(writeup_dir)
    
    def find_recent_articles(self, days: int = 7) -> List[Path]:
        """Find recent signals and digest files."""
        cutoff_date = datetime.now() - timedelta(days=days)
        articles = []
        
        # Find all signals_*.md and digest_*.md files
        for pattern in ['signals_*.md', 'digest_*.md']:
            for filepath in self.writeup_dir.rglob(pattern):
                # Extract date from filename
                match = re.search(r'_(\d{4}-\d{2}-\d{2})\.md', filepath.name)
                if match:
                    file_date = datetime.strptime(match.group(1), '%Y-%m-%d')
                    if file_date >= cutoff_date:
                        articles.append(filepath)
        
        # Sort by date (newest first)
        articles.sort(key=lambda p: self._extract_date(p), reverse=True)
        return articles
    
    def _extract_date(self, filepath: Path) -> datetime:
        """Extract date from filename."""
        match = re.search(r'_(\d{4}-\d{2}-\d{2})\.md', filepath.name)
        if match:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
        return datetime.min
    
    def extract_tickers(self, filepath: Path) -> List[str]:
        """Extract all ticker symbols from an article."""
        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception as e:
            return []
        
        # Extract tickers from signals section (most reliable)
        signals = self.signal_parser.parse_file(filepath)
        tickers = [s.symbol.upper() for s in signals]
        
        # Also extract any $TICKER mentions in the content
        # But filter out numeric-only values (dollar amounts)
        dollar_ticker_pattern = re.compile(r'\$([A-Za-z0-9]{2,10})\b')
        dollar_matches = dollar_ticker_pattern.findall(content)
        
        # Filter out numeric-only matches (dollar amounts like $101983, $10, etc.)
        # Keep only matches that contain at least one letter
        valid_tickers = []
        for match in dollar_matches:
            match_upper = match.upper()
            # Skip if it's purely numeric (dollar amounts)
            if match_upper.isdigit():
                continue
            # Skip common dollar amount patterns (e.g., $10K, $100M, $1B)
            if re.match(r'^\d+[KM]?$', match_upper):
                continue
            # Keep if it contains letters (likely a ticker)
            if any(c.isalpha() for c in match_upper):
                valid_tickers.append(match_upper)
        
        # Combine and deduplicate
        all_tickers = set(tickers + valid_tickers)
        return sorted(list(all_tickers))
    
    def validate_readiness(self, filepath: Path) -> Dict[str, Any]:
        """Validate if an article is ready to send."""
        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception as e:
            return {
                'ready': False,
                'errors': [f'Could not read file: {e}'],
                'warnings': []
            }
        
        errors = []
        warnings = []
        
        # Check for required sections
        has_top_stories = '## 🔥 Top Stories' in content or 'Top Stories' in content
        has_signals = '## 🎯 Trading Signals' in content
        has_backtest = '## 📈 Backtest Results' in content or 'Backtest Results' in content
        
        # Check if signals section has content
        signals = self.signal_parser.parse_file(filepath)
        has_signals_content = len(signals) > 0
        
        # Check for empty signals section
        if has_signals and not has_signals_content:
            errors.append('Signals section exists but contains no valid signals')
        
        # Check for backtest results (should exist for signals files)
        is_signals_file = 'signals_' in filepath.name
        if is_signals_file and not has_backtest:
            warnings.append('Signals file missing backtest results section')
        
        # Check for market snapshot
        has_market_snapshot = '## 💰 Market Snapshot' in content or 'Market Snapshot' in content
        
        # Check for minimum content length
        if len(content.strip()) < 500:
            warnings.append('Article content seems very short (< 500 chars)')
        
        # Check for proper formatting (should have title)
        has_title = content.strip().startswith('#')
        if not has_title:
            warnings.append('Article missing proper title (should start with #)')
        
        # Check for disclaimer
        has_disclaimer = 'Disclaimer' in content or 'disclaimer' in content
        if not has_disclaimer:
            warnings.append('Article missing disclaimer')
        
        # Determine readiness
        ready = len(errors) == 0
        
        return {
            'ready': ready,
            'errors': errors,
            'warnings': warnings,
            'has_top_stories': has_top_stories,
            'has_signals': has_signals,
            'has_signals_content': has_signals_content,
            'has_backtest': has_backtest,
            'has_market_snapshot': has_market_snapshot,
            'signal_count': len(signals),
            'content_length': len(content)
        }


class Command(BaseCommand):
    help = 'Review recent articles for tickers and validate readiness to send'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to look back (default: 7)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information for each article',
        )
        parser.add_argument(
            '--ticker',
            type=str,
            help='Filter by specific ticker symbol (e.g., BTC, ETH)',
        )
        parser.add_argument(
            '--only-errors',
            action='store_true',
            help='Only show articles with errors',
        )

    def handle(self, *args, **options):
        days = options['days']
        verbose = options['verbose']
        ticker_filter = (options.get('ticker') or '').upper()
        only_errors = options['only_errors']
        
        self.stdout.write(self.style.SUCCESS(f'🔍 Reviewing articles from past {days} days...\n'))
        
        reviewer = ArticleReviewer(WRITEUP_DIR)
        
        # Find recent articles
        articles = reviewer.find_recent_articles(days=days)
        
        if not articles:
            self.stdout.write(self.style.WARNING('No articles found in the specified time period.'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'✓ Found {len(articles)} article(s)\n'))
        
        # Review each article
        all_tickers = defaultdict(list)  # ticker -> [articles]
        review_results = []
        
        for article in articles:
            date = reviewer._extract_date(article)
            date_str = date.strftime('%Y-%m-%d')
            
            # Extract tickers
            tickers = reviewer.extract_tickers(article)
            
            # Validate readiness
            validation = reviewer.validate_readiness(article)
            
            # Filter by ticker if specified
            if ticker_filter and ticker_filter not in [t.upper() for t in tickers]:
                continue
            
            # Filter by errors if requested
            if only_errors and validation['ready']:
                continue
            
            # Track tickers
            for ticker in tickers:
                all_tickers[ticker].append(article)
            
            review_results.append({
                'filepath': article,
                'date': date_str,
                'tickers': tickers,
                'validation': validation
            })
        
        # Sort by date (newest first)
        review_results.sort(key=lambda x: x['date'], reverse=True)
        
        # Print summary
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('📊 Review Summary'))
        self.stdout.write('='*80)
        
        ready_count = sum(1 for r in review_results if r['validation']['ready'])
        error_count = len(review_results) - ready_count
        
        self.stdout.write(f'Total articles reviewed: {len(review_results)}')
        self.stdout.write(self.style.SUCCESS(f'✓ Ready to send: {ready_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'✗ Needs attention: {error_count}'))
        self.stdout.write('')
        
        # Print ticker summary
        if all_tickers:
            self.stdout.write(self.style.SUCCESS('📈 Tickers Found:\n'))
            sorted_tickers = sorted(all_tickers.items(), key=lambda x: len(x[1]), reverse=True)
            for ticker, articles_list in sorted_tickers[:20]:  # Top 20
                count = len(articles_list)
                self.stdout.write(f'  ${ticker}: {count} article(s)')
            if len(sorted_tickers) > 20:
                self.stdout.write(f'  ... and {len(sorted_tickers) - 20} more tickers')
            self.stdout.write('')
        
        # Print detailed results
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('📄 Article Details'))
        self.stdout.write('='*80 + '\n')
        
        for result in review_results:
            article = result['filepath']
            date_str = result['date']
            tickers = result['tickers']
            validation = result['validation']
            
            # Article header
            status_icon = '✅' if validation['ready'] else '❌'
            self.stdout.write(f'\n{status_icon} {article.name} ({date_str})')
            self.stdout.write(f'   Path: {article.relative_to(WRITEUP_DIR)}')
            
            # Tickers
            if tickers:
                ticker_str = ', '.join([f'${t}' for t in tickers])
                self.stdout.write(f'   Tickers: {ticker_str} ({len(tickers)} total)')
            else:
                self.stdout.write(self.style.WARNING('   ⚠️  No tickers found'))
            
            # Validation details
            if verbose or not validation['ready']:
                if validation['errors']:
                    self.stdout.write(self.style.ERROR('   Errors:'))
                    for error in validation['errors']:
                        self.stdout.write(self.style.ERROR(f'     • {error}'))
                
                if validation['warnings']:
                    self.stdout.write(self.style.WARNING('   Warnings:'))
                    for warning in validation['warnings']:
                        self.stdout.write(self.style.WARNING(f'     • {warning}'))
                
                if verbose:
                    self.stdout.write('   Details:')
                    self.stdout.write(f'     • Signals: {validation["signal_count"]} found')
                    self.stdout.write(f'     • Content length: {validation["content_length"]:,} chars')
                    self.stdout.write(f'     • Has top stories: {validation["has_top_stories"]}')
                    self.stdout.write(f'     • Has signals section: {validation["has_signals"]}')
                    self.stdout.write(f'     • Has backtest: {validation["has_backtest"]}')
                    self.stdout.write(f'     • Has market snapshot: {validation["has_market_snapshot"]}')
        
        # Final summary
        self.stdout.write('\n' + '='*80)
        if ready_count == len(review_results):
            self.stdout.write(self.style.SUCCESS('✓ All articles are ready to send!'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️  {error_count} article(s) need attention before sending.'))
        self.stdout.write('='*80 + '\n')
