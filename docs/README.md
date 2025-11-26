# 📚 Squid Digest Documentation

Complete documentation index for developers, contributors, and users of Squid Digest.

## Table of Contents

### Getting Started
- **[USAGE.md](USAGE.md)** - User guide for running and using Squid Digest
- **[TECHNICAL.md](TECHNICAL.md)** - Complete technical documentation, architecture, and setup guide

### Development
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Guidelines for contributing to the project
- **[TECHNICAL.md](TECHNICAL.md)** - Architecture details, testing, and deployment

### Security
- **[SECURITY.md](SECURITY.md)** - Security policy and vulnerability reporting
- **[SECURITY_AUDIT.md](SECURITY_AUDIT.md)** - Pre-publication security audit details

### Setup Guides
- **[TELEGRAM_SETUP.md](TELEGRAM_SETUP.md)** - Configure Telegram bot integration
- **[GITHUB_ACTIONS_EMAIL_SETUP.md](GITHUB_ACTIONS_EMAIL_SETUP.md)** - GitHub Actions email automation setup

### Project Context
- **[SQUID_DIGEST_HANDOFF.md](SQUID_DIGEST_HANDOFF.md)** - Project context, history, and handoff notes
- **[GIT_HISTORY_CLEANUP.md](GIT_HISTORY_CLEANUP.md)** - Pre-publication git history cleanup notes

### Other
- **[PRE_PUBLICATION_CHECKLIST.md](PRE_PUBLICATION_CHECKLIST.md)** - Checklist for making the repository public
- **[WHITESPACE_RENDERING_GUIDE.md](WHITESPACE_RENDERING_GUIDE.md)** - Guide for whitespace rendering in markdown

---

## 🏗️ Technical Architecture

### Impressive Technical Achievements

**Multi-LLM Provider Abstraction**
- Clean, extensible provider pattern supporting Perplexity and OpenAI
- Easy to add new LLM providers without code changes
- Environment-based configuration with fallbacks

**Sophisticated Backtest Engine**
- Incremental backtesting with state persistence across runs
- Dual-strategy support (Buy the News & Sell the News)
- Real-time portfolio tracking with position management
- Historical price data caching for performance
- Benchmark comparisons against BTC, BTC+ETH, and BTC+ETH+OPEN

**Production-Ready Automation**
- Fully automated daily pipeline via GitHub Actions
- Ghost CMS integration for publishing
- Email distribution to subscribers
- Telegram notifications for instant updates
- Self-updating README with latest signals

**Code Quality & Security**
- Comprehensive security audit completed before public release
- All credentials managed via environment variables
- Git history scrubbed of sensitive data
- Type hints throughout codebase
- Extensive test coverage

### System Flow

```
┌─────────────────┐
│  Leviathan News │ ──> Fetch top headlines
│  ([API](https://api.leviathannews.xyz)) │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  LLM Provider    │ ──> Generate trading signals
│  (Perplexity)    │     Analyze sentiment
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  Backtest Engine │ ──> Test strategies
│  - Portfolio     │     Track performance
│  - Price Fetcher│     Compare benchmarks
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  Publishing      │ ──> Ghost CMS
│  - Ghost         │     Email subscribers
│  - Telegram      │     Update README
│  - GitHub        │
└─────────────────┘
```

---

## 🚀 Quick Start

### Installation

This project uses [`uv`](https://github.com/astral-sh/uv) for fast, reliable dependency management.

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/your-org/squid-digest.git
cd squid-digest

# Install dependencies
uv sync

# Configure environment
cp env.template .env
# Edit .env with your API keys

# Run Django migrations (if using Django features)
uv run python manage.py migrate
```

### Running the Digest

```bash
# Generate and publish digest (production)
uv run python manage.py pull_news --limit 10

# Test mode with dry run (no API calls or publishing)
uv run python manage.py pull_news --test --dry-run
```

For more detailed setup instructions, see [TECHNICAL.md](TECHNICAL.md).

---

## 🤖 Credits & AI Collaboration

This project showcases "vibe coding" - the collaborative dance between human creativity and AI capabilities. This is the first fully AI "vibe coded" repository in the Leviathan News ecosystem.

**Built With:**
- **Claude (Anthropic)** - Architecture, implementation, testing, documentation
- **Cursor AI** - Rapid prototyping and code generation
- **ChatGPT (OpenAI)** - Problem-solving and alternative perspectives
- **Human Oversight** - Vision, decisions, security, validation

**Development Timeline:**
- Initial prototype: 4 hours
- Full feature set: 2 days
- Testing & docs: 1 day
- **Total:** ~3 days of AI-accelerated development

**Key Insight:** AI excels at boilerplate, tests, and standard patterns. Humans remain essential for security, architecture, and judgment calls. Together? Genuinely transformative. 🏴‍☠️

### Lessons Learned

1. **AI accelerates iteration** - From idea to working code in hours vs days
2. **Comprehensive documentation** - Comes naturally with AI assistance
3. **Security review is critical** - AI can't replace human vigilance
4. **Iterative refinement** - Produces better results than one-shot prompts
5. **Multiple AI models** - Provide valuable different perspectives

The collaboration between multiple AI tools (Claude, Cursor, ChatGPT) and human oversight created a production-ready system in record time, demonstrating the power of AI-assisted development when combined with careful human review and security practices.

---

## 📖 Documentation Overview

### For Users
Start with **[USAGE.md](USAGE.md)** to learn how to run and use Squid Digest.

### For Developers
- **[TECHNICAL.md](TECHNICAL.md)** - Complete technical reference
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines

### For System Administrators
- **[TELEGRAM_SETUP.md](TELEGRAM_SETUP.md)** - Telegram bot configuration
- **[GITHUB_ACTIONS_EMAIL_SETUP.md](GITHUB_ACTIONS_EMAIL_SETUP.md)** - CI/CD email setup
- **[SECURITY.md](SECURITY.md)** - Security policies and reporting

### For Contributors
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to contribute
- **[SQUID_DIGEST_HANDOFF.md](SQUID_DIGEST_HANDOFF.md)** - Project context and history

---

**Need help?** Check the specific documentation file for your use case, or open an issue on GitHub.
