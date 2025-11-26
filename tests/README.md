# Tests for Squid Digest

This directory contains tests to verify functionality and catch regressions.

## Test Files

### Unit Tests
- `test_email_formatting.py` - Tests for email subject line, H1, and HTML formatting
- `test_post_status.py` - Tests for post status (published vs draft)
- `test_telegram_formatting.py` - Tests for Telegram HTML entity handling

### Integration Tests
- `test_telegram_integration.py` - Full flow tests for Telegram formatting and posting
  - Tests formatting real signals files
  - Tests message splitting logic
  - Tests HTML entity handling
  - Tests error cases

- `test_digest_generation.py` - Tests for digest generation pipeline
  - Tests script existence and importability
  - Tests required modules can be imported
  - Tests signals file format validation

- `test_github_workflow_simulation.py` - Tests that simulate GitHub workflow steps
  - Tests exact workflow imports
  - Tests file reading logic
  - Tests formatting workflow
  - Tests error handling scenarios

## Running Tests

### Option 1: Using the test runner script (recommended)

```bash
# Install dependencies first
pip install -r requirements.txt
pip install -e .

# Run all tests
python scripts/run_all_tests.py
```

### Option 2: Using pytest

```bash
# Install dependencies first
pip install -r requirements.txt
pip install -e .

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_telegram_integration.py -v
```

### Option 3: Using unittest directly

```bash
# Install dependencies first
pip install -r requirements.txt
pip install -e .

# Run tests
python -m unittest discover tests/ -v
```

### Option 4: Run individual test files

```bash
cd tests
python test_telegram_integration.py
python test_digest_generation.py
python test_github_workflow_simulation.py
```

## Pre-commit Hooks

Pre-commit hooks are configured to run tests automatically before commits. To set up:

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Run hooks manually on all files
pre-commit run --all-files
```

The pre-commit hooks will:
1. Check Python syntax with ruff
2. Run all tests
3. Check Python file syntax with py_compile

## Test Coverage

The tests verify:

### Email Functionality
1. ✅ Email subject line uses squid emoji (🦑) and "Leviathan News Daily Digest"
2. ✅ H1 in email template uses squid emoji and correct text
3. ✅ Posts are created with `status="published"` (not draft) when sending digest email
4. ✅ Blockquotes don't have quotes around comment text
5. ✅ Blockquotes don't have em dashes before username
6. ✅ Username links point to `/articles` (not `/comments`)
7. ✅ Footer and disclaimer are placed after backtest section
8. ✅ Backtest formatting uses bullet points
9. ✅ Cash is included in main backtest section (not duplicated)

### Telegram Functionality
10. ✅ Telegram HTML entities are not double-escaped
11. ✅ Real signals files can be formatted correctly
12. ✅ Messages are split when exceeding Telegram limit (4096 chars)
13. ✅ HTML tags are properly balanced
14. ✅ Tables are converted to list format
15. ✅ Error handling works correctly

### Digest Generation
16. ✅ Digest script exists and is importable
17. ✅ Required modules can be imported
18. ✅ Signals files follow expected naming pattern (signals_YYYY-MM-DD.md)

### GitHub Workflow
19. ✅ Workflow imports work correctly
20. ✅ File reading logic works
21. ✅ Formatting workflow works
22. ✅ Error handling scenarios are handled gracefully

## Troubleshooting

### Import Errors
If you get import errors, make sure:
1. Dependencies are installed: `pip install -r requirements.txt`
2. Package is installed in editable mode: `pip install -e .`
3. You're running from the project root directory

### Test Failures
- Check that signals files exist in `writeup/` directory
- Some tests require Telegram credentials (they will skip if not available)
- Integration tests use real files from `writeup/` directory

### Pre-commit Hook Issues
- Make sure pre-commit is installed: `pip install pre-commit`
- Reinstall hooks: `pre-commit uninstall && pre-commit install`
- Run manually to see errors: `pre-commit run --all-files`
