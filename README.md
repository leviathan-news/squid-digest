# squid-digest

AI-powered daily digest generator that pulls top headlines from Leviathan News, processes them through LLM provider, and publishes to Ghost.

## Features

- 🔥 Fetches crypto/tech news from Leviathan News API 
- 🤖 Generates intelligent digests using Perplexity AI (with OpenAI/Claude support)
- 📝 Save writeup for each news content or bundle all news content
- 📧 Automated email delivery via Ghost CMS with GitHub Actions
- ⏰ Scheduled daily digest generation (5 AM PT draft, 6 AM PT send)
- ✏️ Admin review workflow with edit notifications

## Quickstart

### Setup

- With [uv](https://docs.astral.sh/uv/getting-started/installation/)
```bash
uv sync
```

- With [venv](https://docs.python.org/3/library/venv.html)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp env.template .env
# Edit .env with your API keys (PERPLEXITY_API_KEY and GHOST_ADMIN_API_KEY are required)
```


### Run digest pipeline

- Fetch (5) news contents, bundle all to one writeup
```bash
python scripts/digest.py
```

### Email Automation Setup

The project includes automated email delivery via GitHub Actions and Ghost CMS:

#### 1. Ghost CMS Setup
1. Ensure your Ghost site is set up and accessible
2. Generate an Admin API key in Ghost dashboard (Settings → Integrations → Add custom integration)
3. Add `GHOST_URL` and `GHOST_ADMIN_API_KEY` to your `.env` file

#### 2. GitHub Secrets Configuration
Configure these secrets in your GitHub repository settings:
- `GHOST_URL`: Your Ghost site URL
- `GHOST_ADMIN_API_KEY`: Your Ghost Admin API key
- `PERPLEXITY_API_KEY`: Your Perplexity API key
- `ADMIN_EMAILS`: Comma-separated admin emails (optional, defaults to ghall1@gmail.com)
- `PUBLIC_EMAILS`: Comma-separated public recipient emails (optional, defaults to ghall1@gmail.com,curvedefi@gmail.com)

#### 3. Automated Schedule
- **5:00 AM PT**: Generates daily digest draft and emails admins for review
- **6:00 AM PT**: Sends digest to public email list
- **Edit Detection**: If admins edit the draft between 5-6 AM PT, all admins are notified

#### 4. Manual Email Testing
Test email functionality locally:
```bash
# Test admin notification
python scripts/send_email.py --type admin --digest-file writeup/trading_signals_2025-01-15.md --github-url https://github.com/user/repo/blob/main/writeup/file.md

# Test public digest
python scripts/send_email.py --type public --digest-file writeup/trading_signals_2025-01-15.md

# Dry run (no actual email sent)
python scripts/send_email.py --type admin --digest-file writeup/trading_signals_2025-01-15.md --github-url https://github.com/user/repo/blob/main/writeup/file.md --dry-run
```



## Architecture

```
squid_digest/
├── config.py                       # Configuration management (LLM providers, API keys)
├── core/                           # Core business logic
│   └── digest_engine.py            # Main digest generation pipeline
├── llm/                            # LLM provider implementations
│   └── providers.py                # OpenAI, Claude, Perplexity providers
├── tools/                          # External service integrations
│   └── leviathan.py                # Leviathan News API client
└── context/                        # Context and prompt management
    └── prompts/
        └── template.py             # System prompts and templates
```

### `tools/leviathan`
- Fetch news from Leviathan News API
- Get redirect url for each news
- **Fetch news content from each news**

### Tracability
- Langfuse for tracing the pipeline


### LLM Providers
Perplexity AI (default), OpenAI, and Claude can be switched easily via `LLM_CHAT_PROVIDER` environment variable