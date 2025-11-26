"""
Django management command to preview today's newsletter.

This command:
1. Generates today's newsletter (if not already generated)
2. Displays a formatted preview of the content
"""

import re
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand
from squid_digest.config import WRITEUP_DIR, get_writeup_file_path


class Command(BaseCommand):
    help = 'Preview newsletter (reads existing files only, use --generate to create new files)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Preview newsletter for specific date (YYYY-MM-DD). Defaults to today.',
        )
        parser.add_argument(
            '--generate',
            action='store_true',
            help='Force regeneration of newsletter even if it exists',
        )
        parser.add_argument(
            '--full',
            action='store_true',
            help='Show full content (default shows first 2000 chars)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview without generating files (only shows existing newsletter)',
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        force_generate = options.get('generate', False)
        show_full = options.get('full', False)
        dry_run = options.get('dry_run', False)
        
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                self.stdout.write(self.style.ERROR(f'Invalid date format: {date_str}. Use YYYY-MM-DD'))
                return
        else:
            target_date = datetime.now()
        
        date_formatted = target_date.strftime('%Y-%m-%d')
        
        # Try to find existing newsletter file
        # Check for both signals_ and digest_ formats
        signals_file = get_writeup_file_path(f'signals_{date_formatted}.md', target_date)
        digest_file = get_writeup_file_path(f'digest_{date_formatted}.md', target_date)
        
        newsletter_file = None
        if signals_file.exists():
            newsletter_file = signals_file
        elif digest_file.exists():
            newsletter_file = digest_file
        
        # Generate if needed (only if explicitly requested)
        if not newsletter_file or force_generate:
            if not force_generate:
                # Default behavior: don't generate, just show what exists
                self.stdout.write(self.style.WARNING('📝 Newsletter not found.'))
                self.stdout.write(self.style.WARNING('   Safe mode: Not generating to avoid local file contamination.'))
                self.stdout.write('   💡 Tip: Use --generate to actually generate (or let GitHub Actions handle it)')
                return
            elif dry_run:
                self.stdout.write(self.style.WARNING('📝 Newsletter not found.'))
                self.stdout.write(self.style.WARNING('   DRY RUN: Would generate newsletter, but skipping to avoid local file contamination.'))
                self.stdout.write('   💡 Tip: Use --generate (without --dry-run) to actually generate')
                return
            else:
                self.stdout.write(self.style.WARNING('📝 Newsletter not found or regeneration requested...'))
                self.stdout.write('   Generating newsletter (this may take a minute)...\n')
                
                import subprocess
                import sys
                
                # Run the digest script
                result = subprocess.run(
                    [sys.executable, 'scripts/digest.py', '--no-fetch', '--no-fetch-tokens'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    self.stdout.write(self.style.ERROR('Failed to generate newsletter:'))
                    self.stdout.write(result.stderr)
                    return
                
                # Check again for the generated file
                if signals_file.exists():
                    newsletter_file = signals_file
                elif digest_file.exists():
                    newsletter_file = digest_file
                else:
                    self.stdout.write(self.style.ERROR('Newsletter generation completed but file not found.'))
                    return
        
        if not newsletter_file or not newsletter_file.exists():
            self.stdout.write(self.style.ERROR(f'Newsletter not found for {date_formatted}'))
            self.stdout.write(f'   Expected: {signals_file} or {digest_file}')
            return
        
        # Read and display the newsletter
        try:
            content = newsletter_file.read_text(encoding='utf-8')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to read newsletter: {e}'))
            return
        
        # Display preview
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'📰 Newsletter Preview - {target_date.strftime("%B %d, %Y")}'))
        self.stdout.write('='*80)
        self.stdout.write(f'File: {newsletter_file.relative_to(WRITEUP_DIR)}')
        self.stdout.write(f'Size: {len(content):,} characters\n')
        
        # Extract key sections for summary
        has_top_stories = '## 🔥 Top Stories' in content
        has_signals = '## 🎯 Trading Signals' in content
        has_backtest = '## 📈 Backtest Results' in content
        has_market_snapshot = '## 💰 Market Snapshot' in content
        
        # Count signals if present
        signal_count = 0
        if has_signals:
            signal_pattern = re.compile(r'\*\*\$([A-Za-z0-9]+)\s+[^:]+?:\s+([A-Z\s]+)\*\*')
            signal_count = len(signal_pattern.findall(content))
        
        self.stdout.write(self.style.SUCCESS('📊 Content Summary:'))
        self.stdout.write(f'  ✓ Top Stories: {"Yes" if has_top_stories else "No"}')
        self.stdout.write(f'  ✓ Market Snapshot: {"Yes" if has_market_snapshot else "No"}')
        self.stdout.write(f'  ✓ Trading Signals: {"Yes" if has_signals else "No"}')
        if has_signals:
            self.stdout.write(f'     → {signal_count} signal(s) found')
        self.stdout.write(f'  ✓ Backtest Results: {"Yes" if has_backtest else "No"}')
        self.stdout.write('')
        
        # Show content preview
        if show_full:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.SUCCESS('📄 Full Content:'))
            self.stdout.write('='*80 + '\n')
            self.stdout.write(content)
        else:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.SUCCESS('📄 Content Preview (first 2000 chars):'))
            self.stdout.write('='*80 + '\n')
            
            # Show first part
            preview = content[:2000]
            self.stdout.write(preview)
            
            if len(content) > 2000:
                self.stdout.write('\n' + '...' + f' ({len(content) - 2000:,} more characters)')
                self.stdout.write(self.style.WARNING('\n💡 Use --full to see complete content'))
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('✓ Preview complete'))
        self.stdout.write('='*80 + '\n')
