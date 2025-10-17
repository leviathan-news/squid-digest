# Squid Digest - Usage Guide

## Overview
Squid Digest automatically generates AI-powered daily digests from Leviathan News and publishes them to Ghost.

## Setup

### 1. Run the setup script
```bash
./setup.sh
```

### 2. Configure your API keys
Edit the `.env` file with your actual keys:
```bash
PERPLEXITY_API_KEY=pplx-your-actual-key-here
GHOST_URL=https://your-ghost-site.com
GHOST_ADMIN_API_KEY=your-ghost-admin-key
LLM_CHAT_PROVIDER=perplexity  # Default provider
```

## Commands

### Test Mode (Recommended First)
Test the full workflow without making API calls or publishing:
```bash
python manage.py pull_news --test --dry-run
```

### Preview Digest (Real Data)
Fetch real news and generate digest, but don't publish:
```bash
python manage.py pull_news --limit 10 --dry-run
```

### Full Production Run
Fetch news, generate digest, and publish to Ghost:
```bash
python manage.py pull_news --limit 10
```

## Command Options

- `--limit N` : Number of news items to fetch (default: 10)
- `--test` : Use built-in test data instead of API
- `--dry-run` : Generate digest but don't publish to Ghost

## What It Does

1. **Fetches** top trending news from Leviathan News API
2. **Analyzes** headlines using Perplexity AI ("sonar" model) by default
3. **Generates** a professional newsletter-style digest with:
   - Compelling subject line
   - Brief intro
   - Story summaries with analysis
   - Key trends and insights
4. **Publishes** to Ghost as a published post (unless --dry-run)

## LLM Provider Integration

The system uses Perplexity AI by default with the "sonar" model which:
- Has access to real-time web data
- Provides citations and sources
- Generates high-quality analysis
- Costs ~$0.005 per request

You can switch to OpenAI by setting `LLM_CHAT_PROVIDER=openai` in your `.env` file.

## Scheduling (Optional)

To run daily automatically, add to crontab:
```bash
# Run every day at 8 AM
0 8 * * * cd /path/to/squid-digest && /path/to/venv/bin/python manage.py pull_news --limit 10
```

## Troubleshooting

### "PERPLEXITY_API_KEY not configured"
Make sure you've created a `.env` file and added your Perplexity API key.

### "Invalid model" error
The code uses the "sonar" model. If you need a different model, check Perplexity docs and update line 128 in `pull_news.py`.

### Ghost publishing fails
- Verify `GHOST_URL` doesn't have a trailing slash
- Ensure `GHOST_ADMIN_API_KEY` is valid
- Check Ghost API documentation for endpoint changes

## Cost Estimates

- Perplexity API: ~$0.005 per digest (~$1.50/month for daily)
- OpenAI API: ~$0.01-0.03 per digest (varies by model)
- Ghost: Included in your hosting plan
- Leviathan News API: Free

## Example Output

The digest will be formatted as:
- Subject line (used as Ghost post title)
- Introduction paragraph
- 3-4 story analyses
- Key trends section
- Closing remarks

All with professional newsletter styling and insights tailored for crypto/tech professionals.

