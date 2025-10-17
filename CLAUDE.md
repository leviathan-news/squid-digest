# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Squid Digest is a Django-based automation tool that generates AI-powered daily news digests. It fetches trending crypto/tech news from Leviathan News API, processes headlines through Perplexity AI (or OpenAI) to generate intelligent summaries, and publishes the digest to Ghost CMS.

## Python Environment

**Always run Python commands with `uv`** (per user's global CLAUDE.md instructions).

## Key Commands

### Setup
```bash
# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment (copy env.template to .env and fill in API keys)
cp env.template .env
```

### Running the Digest Pipeline
```bash
# Generate and publish digest (production)
python manage.py pull_news --limit 10

# Test mode with dry run (no API calls or publishing)
python manage.py pull_news --test --dry-run

# Fetch real news but don't publish
python manage.py pull_news --limit 10 --dry-run
```

### Django Management
```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server (not typically needed for this project)
python manage.py runserver
```

### Code Quality
```bash
# Format code
black .

# Lint code
flake8 .

# Sort imports
isort .
```

## Architecture

The codebase follows a layered architecture with clear separation of concerns:

```
digest/management/commands/pull_news.py    ← Django CLI command (orchestration layer)
         ↓
digest/services/digest_service.py          ← Business logic (service layer)
         ↓
digest/clients/                             ← API clients (data access layer)
    ├── leviathan.py                        ← Fetches news from Leviathan API
    ├── perplexity.py                       ← Generates AI content
    └── ghost.py                            ← Publishes to Ghost CMS
```

### Layer Responsibilities

**1. Command Layer** ([pull_news.py](digest/management/commands/pull_news.py))
- Entry point via Django management command
- Handles CLI arguments (`--limit`, `--dry-run`, `--test`)
- Manages output formatting and error display
- Orchestrates the pipeline by calling the service layer

**2. Service Layer** ([digest_service.py](digest/services/digest_service.py))
- Contains business logic for digest generation
- Orchestrates the 3-step pipeline: fetch → generate → publish
- Formats news items into AI prompts
- Extracts title/body from AI responses

**3. Client Layer** ([digest/clients/](digest/clients/))
- **LeviathanNewsClient** ([leviathan.py](digest/clients/leviathan.py)): Fetches news from https://api.leviathannews.xyz
- **PerplexityClient** ([perplexity.py](digest/clients/perplexity.py)): Calls Perplexity AI API with "sonar" model (default)
- **OpenAIClient** ([openai.py](digest/clients/openai.py)): Alternative OpenAI API client
- **GhostClient** ([ghost.py](digest/clients/ghost.py)): Publishes posts to Ghost CMS via Admin API

### Data Flow

```
User runs: python manage.py pull_news --limit 10

1. Command.handle()
   → initializes clients (Leviathan, Perplexity, Ghost)
   → creates DigestService with clients

2. DigestService.fetch_news()
   → LeviathanNewsClient.fetch_top_news()
   → returns list of news items

3. DigestService.generate_digest(items)
   → formats items into prompt
   → PerplexityClient.generate_completion(prompt) (or OpenAI if configured)
   → returns AI-generated digest text

4. DigestService.publish_digest(content)
   → parses title from first line
   → GhostClient.create_post(title, content)
   → publishes to Ghost CMS
```

### Django Structure
- **Project name**: `config` (Django uses this instead of a typical project folder)
- **Main app**: `digest` - single-purpose app for digest generation
- **Database**: SQLite configured but unused (no models defined)
- **Settings**: Loads environment variables via python-dotenv from `.env` file
- **Web component**: Minimal (just `/health/` endpoint and Django admin)

### Configuration
All configuration via environment variables in `.env`:
- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `TIME_ZONE` - Django settings
- `PERPLEXITY_API_KEY` - Perplexity AI authentication (default)
- `OPENAI_API_KEY` - OpenAI authentication (optional)
- `LLM_CHAT_PROVIDER` - LLM provider selection (perplexity/openai)
- `GHOST_URL`, `GHOST_ADMIN_API_KEY` - Ghost CMS configuration

### External APIs
- **Leviathan News**: Public API, no auth required, returns trending crypto/tech news
- **Perplexity AI**: Requires API key, uses "sonar" model for completions (default)
- **OpenAI**: Requires API key, uses GPT models for completions (optional)
- **Ghost Admin API**: Requires URL and Admin API key for post creation

## Development Patterns

### Test Mode
Use `--test` flag to use hardcoded test data instead of API calls ([pull_news.py:100-121](digest/management/commands/pull_news.py#L100-L121)). Combine with `--dry-run` for complete offline testing.

### Error Handling
- All API clients use httpx with configured timeouts
- Clients raise exceptions on failures (HTTPStatusError, etc.)
- Command layer catches exceptions and exits with proper error messages

### Adding New Features
- **New API integration**: Create new client in `digest/clients/`
- **New business logic**: Add to `DigestService` or create new service
- **New command**: Add to `digest/management/commands/`
