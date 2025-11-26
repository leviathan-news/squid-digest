# Squid Digest Bot - Handoff Documentation

## Project Overview
Squid Digest is an AI-powered crypto newsletter that generates daily trading signals and market analysis using Perplexity's reasoning model. The system fetches news from Leviathan News, processes it through AI, and publishes formatted digests via Ghost CMS.

## Current Architecture

### Core Components
- **News Fetcher**: `src/squid_digest/tools/leviathan.py` - Fetches crypto news from [Leviathan News API](https://api.leviathannews.xyz)
- **LLM Provider**: `src/squid_digest/llm/providers.py` - PerplexityChatProvider with reasoning model support
- **Digest Engine**: `src/squid_digest/core/digest_engine.py` - Orchestrates the generation pipeline
- **Email Client**: `src/squid_digest/email/ghost_client.py` - Ghost CMS integration for email publishing
- **Main Script**: `scripts/digest.py` - Entry point for digest generation

### Key Features
- **Dual Content Types**: Generates both "signals" and "digest" versions using different prompts
- **Thinking Logs**: Extracts and logs Perplexity's internal reasoning from `<think>` tags
- **Ghost Integration**: Creates drafts in Ghost CMS for admin review
- **GitHub Actions**: Automated daily generation at 5 AM PT

## Recent Issues & Fixes

### 1. Perplexity Reasoning Model Integration ✅ FIXED
**Problem**: Perplexity's `sonar-reasoning-pro` model outputs internal reasoning in `<think>` tags that appeared in final digests.

**Solution**: Modified `PerplexityLangChainModel` to:
- Extract content between `<think>` and `</think>` tags
- Handle unclosed `<think>` tags (extract everything after `<think>`)
- Save thinking content to `writeup/thinking_logs/{prompt_type}_{date}_thinking.log`
- Return cleaned content without think tags

### 2. GitHub Actions Dependency Issues ✅ FIXED
**Problem**: Workflows failing with `ModuleNotFoundError: No module named 'langchain.callbacks'`

**Root Cause**: Version incompatibility between `langfuse 3.7.0` and `langchain 1.0.0`

**Solution**: 
- Made `langfuse` optional in `digest_engine.py`
- Downgraded to compatible versions: `langchain==0.3.27`, `langchain-openai==0.3.35`
- Updated `requirements.txt` with compatible versions
- Added GitHub Actions permissions: `contents: write`

### 3. Missing Signals Generation ✅ FIXED
**Problem**: Workflow only generated `digest_2025-10-19.md`, missing `signals_2025-10-19.md`

**Root Cause**: Module modification approach didn't persist across processes

**Solution**: 
- Use environment variables: `ACTIVE_PROMPT=signals python scripts/digest.py`
- Updated `scripts/digest.py` to read `ACTIVE_PROMPT` from environment
- Workflow now generates both versions in same run

### 4. Ghost Draft Content Issue ✅ FIXED
**Problem**: Ghost drafts contained notification emails instead of actual digest content

**Solution**: 
- Modified workflow to read markdown files and convert to HTML
- Creates drafts with full formatted content using `format_digest_html()`
- Both signals and digest drafts appear in Ghost admin panel

### 5. Date Mismatch in Drafts ✅ FIXED
**Problem**: Ghost drafts used files from different dates (signals_2025-10-17 + digest_2025-10-19)

**Solution**: 
- Use specific date instead of "most recent" file search
- `TODAY=$(date -u '+%Y-%m-%d')` then look for `signals_${TODAY}.md` and `digest_${TODAY}.md`

## Current Workflow

### Daily Generation (5 AM PT)
1. **Generate Signals**: `ACTIVE_PROMPT=signals python scripts/digest.py` → `signals_YYYY-MM-DD.md`
2. **Generate Digest**: `ACTIVE_PROMPT=digest python scripts/digest.py` → `digest_YYYY-MM-DD.md`
3. **Create Ghost Drafts**: Both files converted to HTML and saved as drafts
4. **Commit Files**: Both markdown files committed to repository
5. **Admin Review**: Drafts appear in Ghost admin panel for review

### Manual Testing
```bash
# Test locally
source venv/bin/activate
ACTIVE_PROMPT=signals python scripts/digest.py --verbose
ACTIVE_PROMPT=digest python scripts/digest.py --verbose

# Send test emails
python scripts/send_email.py --type public --digest-file writeup/signals_2025-10-19.md
python scripts/send_email.py --type public --digest-file writeup/digest_2025-10-19.md
```

## Configuration

### Environment Variables
- `PERPLEXITY_API_KEY` - Required for AI generation
- `GHOST_URL` - Ghost CMS URL
- `GHOST_ADMIN_API_KEY` - Ghost admin API key
- `ADMIN_EMAILS` - Comma-separated admin emails
- `PUBLIC_EMAILS` - Comma-separated public subscriber emails
- `ACTIVE_PROMPT` - Override prompt type (signals/digest)

### Key Files
- `src/squid_digest/context/prompts/template.py` - Contains `SIGNALS_MESSAGE` and `DIGEST_MESSAGE` prompts
- `src/squid_digest/llm/providers.py` - PerplexityChatProvider with thinking extraction
- `.github/workflows/draft-digest.yml` - Daily generation workflow
- `.github/workflows/send-digest.yml` - Daily email sending workflow

## Known Issues & Future Improvements

### Current Limitations
1. **Manual Ghost Publishing**: Drafts are created but require manual publishing
2. **No Email Automation**: Ghost email delivery needs manual configuration
3. **Single Timezone**: Hardcoded to PT timezone
4. **No Content Validation**: No automated quality checks

### Potential Enhancements
1. **Auto-publish**: Automatically publish approved drafts
2. **Content Validation**: Add quality checks for generated content
3. **Multi-timezone Support**: Support different timezones for different audiences
4. **A/B Testing**: Test different prompts and measure engagement
5. **Analytics Integration**: Track open rates, click-through rates, etc.

## Troubleshooting

### Common Issues
1. **Missing Dependencies**: Run `pip install -r requirements.txt`
2. **API Key Issues**: Check environment variables are set correctly
3. **Git Push Failures**: Ensure GitHub Actions has `contents: write` permission
4. **Ghost API Errors**: Verify `GHOST_URL` and `GHOST_ADMIN_API_KEY` are correct

### Debug Commands
```bash
# Check environment
python -c "import os; print('PERPLEXITY_API_KEY:', bool(os.getenv('PERPLEXITY_API_KEY')))"

# Test Ghost connection
python -c "from squid_digest.email import GhostEmailClient; GhostEmailClient()"

# Check generated files
ls -la writeup/
ls -la writeup/thinking_logs/
```

## Success Criteria
The system is working correctly when:
- ✅ Both `signals_YYYY-MM-DD.md` and `digest_YYYY-MM-DD.md` are generated daily
- ✅ Ghost drafts contain full formatted content (not just notifications)
- ✅ Thinking logs are saved to `writeup/thinking_logs/`
- ✅ GitHub Actions runs successfully without errors
- ✅ Files are committed to repository automatically

## Final Notes
The system is currently stable and working as intended. The main workflow generates both content types, creates proper Ghost drafts, and commits files automatically. Future improvements should focus on automation and analytics rather than core functionality fixes.







