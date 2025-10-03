# squid-digest

AI-powered daily digest generator that pulls top headlines from Leviathan News, processes them through LLM provider, and publishes to Ghost.

## Features

- 🔥 Fetches crypto/tech news from Leviathan News API 
- 🤖 Generates intelligent digests using OpenAI / Claude / Perplexity AI
- 📝 Save writeup for each news content or bundle all news content
- 📧 Publishes digest directly to Ghost CMS

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
cp .env.example .env
# Edit .env with your API keys
```


### Run digest pipeline

- Fetch all news contents, bundle all to one writeup
```bash
python scripts/digest.py --fetch-news --bundle-writeup
# or simply as fetch-news and bundle-writeup are defaulted
python scripts/digest.py
```

- Fetch all news contents, save writeup for each news content
```bash
python scripts/digest.py --fetch-news --each-news
# or
uv run scripts/digest.py --fetch-news --each-news
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
OpenAI, Claude, Perplexity can be switched easily