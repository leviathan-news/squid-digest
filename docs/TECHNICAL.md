# 🏴‍☠️ Squid Digest - Technical Documentation

Complete technical guide for developers, contributors, and system administrators.

## Table of Contents

1. [Quickstart](#quickstart)
2. [Architecture](#architecture)
3. [Testing](#testing)
4. [Deployment](#deployment)
5. [Troubleshooting](#troubleshooting)
6. [Additional Documentation](#additional-documentation)

---

## Quickstart

### Prerequisites

- Python 3.11+
- Virtual environment tool ([uv](https://docs.astral.sh/uv/) or venv)
- API keys: Perplexity AI, Ghost CMS Admin
- Optional: Telegram Bot Token, OpenAI API key

### Installation

#### Option 1: Using uv (Recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/leviathan-news/squid-digest.git
cd squid-digest

# Install dependencies
uv sync
```

#### Option 2: Using venv

```bash
# Clone repository
git clone https://github.com/leviathan-news/squid-digest.git
cd squid-digest

# Install dependencies using uv (project standard)
# uv automatically manages the virtual environment
uv sync
```

### Configuration

```bash
# Copy environment template
cp env.template .env

# Edit .env with your API keys
# Required:
#   - PERPLEXITY_API_KEY
#   - GHOST_URL
#   - GHOST_ADMIN_API_KEY
# Optional:
#   - OPENAI_API_KEY (if using OpenAI provider)
#   - TELEGRAM_BOT_TOKEN
#   - TELEGRAM_CHANNEL_ID
```

### Run Digest Pipeline

```bash
# Generate daily digest (uses cached data if available)
python scripts/digest.py

# Generate with verbose logging
python scripts/digest.py --verbose

# Force fetch fresh news (ignore cache)
python scripts/digest.py --no-fetch-tokens

# Test email sending (dry run)
python scripts/send_email.py --type public --digest-file writeup/2025/11/20/signals_2025-11-20.md --dry-run
```

---

## Architecture

### Project Structure

```
squid-digest/
├── src/squid_digest/              # Main package
│   ├── core/                      # Business logic
│   │   └── digest_engine.py       # Main digest generation pipeline
│   ├── llm/                       # LLM provider implementations
│   │   └── providers.py           # OpenAI, Claude, Perplexity providers
│   ├── tools/                     # External service integrations
│   │   └── leviathan.py           # Leviathan News API client
│   ├── email/                     # Ghost CMS email integration
│   │   └── ghost_client.py        # Ghost Admin API client
│   ├── telegram/                  # Telegram integration
│   │   ├── client.py              # Telegram Bot API client
│   │   └── formatter.py           # Markdown to Telegram HTML converter
│   ├── backtest/                  # Trading signal backtesting
│   │   ├── incremental_backtest.py # Incremental backtest engine
│   │   ├── signal_parser.py       # Parse signals from markdown
│   │   ├── price_fetcher.py       # Fetch historical prices (CoinGecko)
│   │   ├── benchmarks.py          # Calculate benchmark comparisons
│   │   └── newsletter_formatter.py # Format backtest results
│   ├── context/                   # Context and prompt management
│   │   └── prompts/
│   │       └── template.py        # System prompts and templates
│   └── config.py                  # Configuration management
├── scripts/                       # Utility scripts
│   ├── digest.py                  # Main digest generation script
│   ├── update_readme.py           # Update README with daily signals
│   ├── send_email.py              # Manual email sending
│   ├── post_telegram.py           # Manual Telegram posting
│   └── add_subscribers.py         # Add Ghost subscribers
├── tests/                         # Test suite
├── .github/workflows/             # GitHub Actions automation
│   ├── draft-digest.yml           # Daily digest generation (5 AM PT)
│   └── send-digest.yml            # Daily email sending (6 AM PT)
├── writeup/                       # Generated digests (YMD structure)
│   └── YYYY/MM/DD/
│       ├── signals_YYYY-MM-DD.md  # Daily signals
│       └── thinking_logs/         # AI reasoning logs
└── docs/                          # Documentation
```

### Architecture Highlights

**LLM Provider Abstraction**
- Clean interface supporting multiple providers (Perplexity, OpenAI)
- Environment-based provider selection
- Consistent API across all providers
- Easy to extend with new providers

**Backtest Engine Sophistication**
- **Incremental Backtesting**: State persists across runs, allowing continuous backtesting
- **Dual Strategy Support**: Simultaneously tracks "Buy the News" and "Sell the News" strategies
- **Portfolio Management**: Real-time position tracking, cash management, P/L calculation
- **Price Data Caching**: Intelligent caching of CoinGecko API responses
- **Benchmark Comparisons**: Automatic comparison against BTC, BTC+ETH, BTC+ETH+OPEN

**Automation Pipeline**
- **GitHub Actions**: Fully automated daily workflow
- **Self-Updating**: README and writeup index auto-update with latest signals
- **Multi-Channel Publishing**: Ghost CMS, Email, Telegram, GitHub
- **Error Handling**: Graceful degradation and error recovery

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Daily Digest Pipeline                     │
│                      (5:00 AM PT)                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────┐
        │  1. Fetch News from Leviathan API    │
        │     - Top 5 headlines                │
        │     - Full article content           │
        │     - Tags, comments, images         │
        └──────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────┐
        │  2. Fetch Token List                 │
        │     - 50+ tracked tokens             │
        │     - Filter out stablecoins         │
        │     - Get token metadata             │
        └──────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────┐
        │  3. Generate Market Snapshot         │
        │     - BTC, ETH, OPEN prices (24h)    │
        │     - Top 3 gainers/losers           │
        │     - CoinGecko API                  │
        └──────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────┐
        │  4. AI Signal Generation             │
        │     - Perplexity AI (Sonar)          │
        │     - Analyze news sentiment         │
        │     - Generate BUY/SELL/HOLD signals │
        └──────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────┐
        │  5. Backtest Signals                 │
        │     - Buy the News strategy          │
        │     - Sell the News strategy         │
        │     - Calculate P/L, benchmarks      │
        └──────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────┐
        │  6. Generate Markdown Digest         │
        │     - Top Stories (HTML table)       │
        │     - Market Snapshot                │
        │     - Trading Signals                │
        │     - Backtest Results               │
        │     - Disclaimer                     │
        └──────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────┐
        │  7. Update README.md                 │
        │     - Extract headlines              │
        │     - Get portfolio performance      │
        │     - Update above-the-fold section  │
        └──────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────┐
        │  8. Publish & Notify                 │
        │     - Commit to GitHub               │
        │     - Create Ghost CMS draft         │
        │     - Post to Telegram               │
        │     - Email admins                   │
        └──────────────────────────────────────┘
```

### Key Components

#### Digest Engine (`src/squid_digest/core/digest_engine.py`)
- Orchestrates the entire pipeline
- Manages LLM provider interactions
- Handles prompt templating
- Caches intermediate results

#### LLM Providers (`src/squid_digest/llm/providers.py`)
- **Perplexity AI** (default): Uses "sonar" model for news analysis
- **OpenAI**: Alternative provider (GPT-4, GPT-3.5-turbo)
- **Claude**: Anthropic Claude models support
- Easily switchable via `LLM_CHAT_PROVIDER` env var

#### Leviathan News Client (`src/squid_digest/tools/leviathan.py`)
- Fetches trending crypto/tech news
- Retrieves full article content
- Gets token metadata and prices
- Public API, no authentication required

#### Backtest Engine (`src/squid_digest/backtest/incremental_backtest.py`)
- **Buy the News**: Buy on STRONG BUY, sell on SELL
- **Sell the News**: Short on STRONG SELL, cover on BUY
- Tracks portfolio state incrementally
- Compares against benchmarks (BTC, BTC+ETH, BTC+ETH+OPEN)
- Persists state to JSON files

#### Price Fetcher (`src/squid_digest/backtest/price_fetcher.py`)
- Fetches historical prices from CoinGecko
- Maps token symbols to CoinGecko IDs via Leviathan API
- Caches prices locally (`.cache/prices/`)
- Handles rate limiting and retries

### Environment Variables

See `env.template` for all configuration options:

| Variable | Required | Description |
|----------|----------|-------------|
| `PERPLEXITY_API_KEY` | Yes | Perplexity AI API key |
| `GHOST_URL` | Yes | Ghost CMS site URL |
| `GHOST_ADMIN_API_KEY` | Yes | Ghost Admin API key (format: `id:secret`) |
| `LLM_CHAT_PROVIDER` | No | LLM provider (`perplexity`, `openai`, `claude`) |
| `OPENAI_API_KEY` | No | OpenAI API key (if using OpenAI provider) |
| `TELEGRAM_BOT_TOKEN` | No | Telegram bot token |
| `TELEGRAM_CHANNEL_ID` | No | Telegram channel ID (numeric, including `-`) |
| `ADMIN_EMAILS` | No | Comma-separated admin emails |
| `PUBLIC_EMAILS` | No | Comma-separated public subscriber emails |
| `DJANGO_SECRET_KEY` | No | Django secret (for admin panel) |
| `TIME_ZONE` | No | Timezone for scheduling (default: `America/Los_Angeles`) |

---

## Testing

### Running Tests

```bash
# Run all tests (recommended)
python scripts/run_all_tests.py

# Run with pytest
pytest tests/ -v

# Run with unittest
python -m unittest discover tests/ -v

# Run specific test file
pytest tests/test_telegram_integration.py -v
```

### Test Coverage

- **Unit Tests**: Email formatting, Telegram formatting, post status
- **Integration Tests**: Full Telegram flow, digest generation, GitHub workflow simulation
- See [tests/README.md](../tests/README.md) for detailed test documentation

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

The hooks will:
- Check Python syntax with ruff
- Run all tests
- Validate Python file syntax

---

## Deployment

### GitHub Actions Setup

#### 1. Configure Secrets

Go to: **Repository Settings → Secrets and variables → Actions**

Add the following secrets:
- `GHOST_URL`
- `GHOST_ADMIN_API_KEY`
- `PERPLEXITY_API_KEY`
- `TELEGRAM_BOT_TOKEN` (optional)
- `TELEGRAM_CHANNEL_ID` (optional)
- `ADMIN_EMAILS` (optional)
- `PUBLIC_EMAILS` (optional)

#### 2. Automated Schedule

- **5:00 AM PT** (13:00 UTC): `draft-digest.yml`
  - Generates daily digest
  - Updates README
  - Commits to repository
  - Creates Ghost draft
  - Posts to Telegram
  - Emails admins

- **6:00 AM PT** (14:00 UTC): `send-digest.yml`
  - Sends digest to public subscribers via Ghost

#### 3. Manual Trigger

Workflows can be triggered manually:
1. Go to **Actions** tab
2. Select workflow
3. Click **Run workflow**
4. Choose branch and click **Run workflow**

### Local Testing

Test the complete workflow locally:

```bash
# Test digest generation with cached data
python scripts/digest.py --no-fetch

# Test README update
python scripts/update_readme.py --dry-run

# Test email sending (no actual send)
python scripts/send_email.py --type public --digest-file writeup/2025/11/20/signals_2025-11-20.md --dry-run

# Test Telegram posting (no actual send)
python scripts/post_telegram.py writeup/2025/11/20/signals_2025-11-20.md --dry-run
```

---

## Troubleshooting

### Common Issues

#### Import Errors

```bash
# Make sure dependencies are installed
uv sync

# Verify key dependencies
uv run python -c "import langchain_core; print('✓ langchain_core')"
uv run python -c "import httpx; print('✓ httpx')"
```

#### Test Failures

```bash
# Run tests to see what's failing
python scripts/run_all_tests.py

# Check if signals files exist
ls -la writeup/

# Verify directory structure
python -c "from pathlib import Path; print(list(Path('writeup').rglob('*.md'))[:5])"
```

#### Telegram Posting Issues

**Error: "Can't parse entities"**
- HTML tags are malformed
- Check if truncation is working properly
- Verify `truncate_html_safely()` is being used

**Error: "400 Bad Request"**
- Check bot token is correct
- Verify channel ID (should be negative for channels)
- Ensure bot is admin in the channel

**Error: "Message too long"**
- Should be automatically split into multiple messages
- Check `format_for_telegram()` function
- Verify max_length parameter (default: 4096)

#### Email Delivery Issues

**Ghost draft created but email not sent:**
- Verify Ghost newsletter is configured (Settings → Email newsletter)
- Check email service is set up (Mailgun, SendGrid, etc.)
- Ensure members are subscribed to newsletter

**Email subscribers not found:**
- Add subscribers via Ghost admin panel (Members)
- Or use: `python scripts/add_subscribers.py`
- Check for "subscriber" label

#### GitHub Actions Failures

**Workflow fails at "Generate digest" step:**
- Check PERPLEXITY_API_KEY is set in secrets
- Verify API key is valid and has credits
- Review workflow logs for specific error

**Workflow fails at "Commit and push digest" step:**
- Check GITHUB_TOKEN has write permissions
- Verify branch protection rules allow Actions to push
- Review git configuration in workflow

**Workflow fails at "Post to Telegram" step:**
- This step has `continue-on-error: true` - it shouldn't fail the workflow
- Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID secrets
- Review Telegram API error messages

### Debug Mode

Enable verbose logging:

```bash
# Generate digest with verbose logging
python scripts/digest.py --verbose

# See what's being sent to AI
ACTIVE_PROMPT=signals python scripts/digest.py --verbose --no-fetch
```

### Getting Help

If you're stuck:

1. Check [GitHub Issues](https://github.com/leviathan-news/squid-digest/issues)
2. Review [SQUID_DIGEST_HANDOFF.md](SQUID_DIGEST_HANDOFF.md) for project context
3. Check [Security Policy](SECURITY.md) for vulnerability reporting
4. See [Contributing Guide](CONTRIBUTING.md) for contribution guidelines

---

## Additional Documentation

### Quick Links

- [Email Automation Setup](GITHUB_ACTIONS_EMAIL_SETUP.md) - Detailed email configuration
- [Telegram Setup](TELEGRAM_SETUP.md) - Telegram bot setup guide
- [Security Policy](SECURITY.md) - Vulnerability disclosure process
- [Contributing Guide](CONTRIBUTING.md) - How to contribute
- [Project Handoff](SQUID_DIGEST_HANDOFF.md) - Project context and history
- [Git History Cleanup](GIT_HISTORY_CLEANUP.md) - Pre-publication cleanup notes

### External Resources

- [Leviathan News](https://leviathannews.xyz) - News source
- [Perplexity AI](https://www.perplexity.ai) - LLM provider
- [Ghost CMS](https://ghost.org) - Publishing platform
- [CoinGecko API](https://www.coingecko.com/en/api) - Price data

---

**Last Updated:** 2025-11-20
**Maintained by:** [Leviathan News](https://leviathannews.xyz) 🏴‍☠️🦑
