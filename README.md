# squid-digest

AI-powered daily digest generator that pulls top headlines from Leviathan News, processes them through Perplexity AI, and publishes to Ghost.

## Features

- 🔥 Fetches trending crypto/tech news from Leviathan News API
- 🤖 Generates intelligent digests using Perplexity AI
- 📧 Publishes digest directly to Ghost CMS
- 🧪 Test mode for development and debugging
- ⚙️ Configurable via environment variables

## Quickstart

### Automated Setup
```bash
./setup.sh
```

### Manual Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install pip-tools
pip-compile requirements.in
pip install -r requirements.txt

# Configure environment
cp env.template .env
# Edit .env with your API keys
```

## Configuration

Create a `.env` file with the following variables:

```bash
# Django Configuration
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
TIME_ZONE=America/Los_Angeles

# API Keys
PERPLEXITY_API_KEY=your-perplexity-api-key-here
GHOST_URL=https://your-ghost-site.com
GHOST_ADMIN_API_KEY=your-ghost-admin-api-key-here
```

## Usage

### Generate and Send Digest
```bash
python manage.py pull_news --limit 10
```

### Test Mode (Dry Run)
```bash
python manage.py pull_news --test --dry-run
```

### Command Options
- `--limit N`: Number of news items to process (default: 10)
- `--dry-run`: Generate digest but don't send to Ghost
- `--test`: Use test data instead of fetching from API

## How It Works

1. **News Fetching**: Pulls top headlines from Leviathan News API
2. **AI Processing**: Sends headlines to Perplexity AI with a specialized prompt
3. **Digest Generation**: Creates an engaging newsletter-style digest
4. **Ghost Publishing**: Automatically publishes the digest to your Ghost site

## API Keys Required

- **Perplexity API**: Get your key from [perplexity.ai](https://perplexity.ai)
- **Ghost Admin API**: Generate from your Ghost admin panel

## Development

The command includes test data for development. Use `--test --dry-run` to see the digest generation without API calls or publishing.
