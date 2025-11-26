# Security Policy

## 🏴‍☠️ Reporting a Vulnerability

The Squid Digest team takes security seriously. If you discover a security vulnerability, please help us keep the project secure by following responsible disclosure practices.

### How to Report

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report security issues by:

1. **Email**: Send details to the repository maintainers via GitHub (see repository owner)
2. **GitHub Security Advisory**: Use the GitHub Security Advisory feature at:
   - Go to the repository's Security tab
   - Click "Report a vulnerability"
   - Provide detailed information about the vulnerability

### What to Include

When reporting a vulnerability, please provide:

- **Description**: Clear description of the vulnerability and its potential impact
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Affected Versions**: Which versions are affected
- **Potential Fix**: If you have suggestions for remediation
- **Your Contact Info**: How we can reach you for follow-up

### Response Timeline

- **Initial Response**: Within 48 hours of report
- **Status Update**: Within 7 days with assessment and planned fix timeline
- **Fix Release**: Depends on severity and complexity
  - Critical: 1-7 days
  - High: 7-14 days
  - Medium: 14-30 days
  - Low: 30-60 days

## Security Best Practices

### For Users

1. **Never commit `.env` files** - These contain sensitive API keys
2. **Rotate API keys regularly** - Especially after any potential exposure
3. **Use GitHub Secrets** - Store all credentials in GitHub Secrets for Actions
4. **Review permissions** - Ghost Admin API keys have full access to your Ghost site
5. **Monitor usage** - Watch for unexpected API usage on Perplexity, OpenAI, Ghost

### For Contributors

1. **Never hardcode secrets** - Always use environment variables
2. **Review PRs for secrets** - Check that no credentials are accidentally committed
3. **Use `.gitignore`** - Ensure sensitive files are properly excluded
4. **Test security** - Run security tools before submitting PRs
5. **Follow least privilege** - Request minimal permissions necessary

## Known Security Considerations

### API Key Management

This project requires several API keys:
- **Perplexity API Key**: For LLM digest generation (required)
- **Ghost Admin API Key**: Full access to Ghost CMS (required)
- **CoinGecko API Key**: For price data fetching (optional, recommended to avoid rate limits)
- **Telegram Bot Token**: Controls Telegram bot (optional)
- **OpenAI API Key**: For alternative LLM provider (optional)

**All keys must be stored securely and never committed to git.**

See [SECURITY_AUDIT.md](SECURITY_AUDIT.md) for complete security review findings.

### Git History

✅ **Security Audit Completed**: A comprehensive security audit was conducted before public release (see [SECURITY_AUDIT.md](SECURITY_AUDIT.md) for details).

**Historical Issues (Resolved)**:
- ⚠️ A key recovery script (commit 03e376a) was previously in git history - removed
- ⚠️ Hardcoded CoinGecko API key found in git history - scrubbed using `git-filter-repo`
- ✅ All exposed credentials have been removed from git history
- ✅ All API keys have been rotated

**Pre-Publication Cleanup**:
- ✅ Git history scrubbed of all hardcoded credentials
- ✅ All secrets moved to environment variables
- ✅ GitHub Actions configured with proper secrets management

If using this code, always:
1. ✅ Git history has been audited and cleaned (see [SECURITY_AUDIT.md](SECURITY_AUDIT.md))
2. Rotate all API keys when setting up your own instance
3. Ensure your fork doesn't expose any sensitive data
4. Review the security audit document for complete findings

### Dependency Security

This project uses 119+ Python packages. Regular security audits are recommended:

```bash
# Run security audit
pip install pip-audit
pip-audit
```

We recommend running `pip-audit` regularly and keeping dependencies up to date.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < main  | :x:                |

Currently, only the latest `main` branch is actively supported. We recommend always using the latest version.

## Security Contact

For private security concerns, please contact the repository maintainers directly through GitHub.

---

**Remember**: When in doubt about security, ask! It's better to over-communicate than under-communicate when it comes to security issues. 🦑🔒
