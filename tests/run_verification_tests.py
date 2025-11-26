#!/usr/bin/env python3
"""Simple verification tests that check code changes without requiring dependencies."""

import sys
from pathlib import Path

def test_subject_line_and_status():
    """Test that subject line uses squid emoji and posts are published."""
    with open('src/squid_digest/email/ghost_client.py') as f:
        content = f.read()
        assert '🦑 Leviathan News Daily Digest' in content, 'Subject line should have squid emoji'
        assert 'status="published"' in content or "status='published'" in content, 'Should publish posts'
    return True

def test_h1_template():
    """Test that H1 template uses squid emoji."""
    with open('src/squid_digest/email/templates.py') as f:
        content = f.read()
        assert '🦑 Leviathan News Daily Digest' in content, 'H1 should have squid emoji'
    return True

def test_blockquote_formatting():
    """Test that blockquotes don't have quotes and have correct links."""
    with open('src/squid_digest/email/ghost_client.py') as f:
        content = f.read()
        assert '"{comment}"' not in content, 'Blockquote should not have quotes'
        assert '/u/{username}/articles' in content, 'Username should link to /articles'
        assert '/user/{username}/comments' not in content, 'Should not link to /comments'
    return True

def test_footer_placement():
    """Test that footer is placed after backtest section."""
    with open('scripts/digest.py') as f:
        content = f.read()
        backtest_idx = content.find('full_writeup += backtest_section')
        disclaimer_idx = content.find('Disclaimer:')
        assert backtest_idx != -1, 'Backtest append should be found'
        assert disclaimer_idx != -1, 'Disclaimer should be present'
        assert backtest_idx < disclaimer_idx, 'Backtest should come before disclaimer'
    return True

def test_backtest_formatting():
    """Test that backtest uses bullet points and includes cash."""
    with open('src/squid_digest/backtest/newsletter_formatter.py') as f:
        content = f.read()
        assert '- **Portfolio Value:**' in content, 'Should use bullet points'
        assert '- **Cash:**' in content, 'Cash should be in main section'
    return True

def test_telegram_unescaping():
    """Test that Telegram formatter uses html.unescape()."""
    with open('src/squid_digest/telegram/formatter.py') as f:
        content = f.read()
        assert 'html.unescape(' in content, 'Should use html.unescape()'
    return True

def main():
    """Run all verification tests."""
    print('Running comprehensive verification tests...')
    print('=' * 60)
    
    tests = [
        ('Subject line and status', test_subject_line_and_status),
        ('H1 template', test_h1_template),
        ('Blockquote formatting', test_blockquote_formatting),
        ('Footer placement', test_footer_placement),
        ('Backtest formatting', test_backtest_formatting),
        ('Telegram unescaping', test_telegram_unescaping),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f'✓ {name}')
            passed += 1
        except AssertionError as e:
            print(f'✗ {name}: {e}')
            failed += 1
        except Exception as e:
            print(f'✗ {name}: {e}')
            failed += 1
    
    print('=' * 60)
    print(f'Results: {passed} passed, {failed} failed')
    
    if failed == 0:
        print('✅ All tests passed!')
        return 0
    else:
        print('❌ Some tests failed')
        return 1

if __name__ == '__main__':
    # Change to project root
    project_root = Path(__file__).parent.parent
    import os
    os.chdir(project_root)
    
    sys.exit(main())
