# Contributing to Squid Digest 🏴‍☠️🦑

First off, thanks for considering contributing to Squid Digest! This project was built with AI-assisted development, and we welcome contributions from both humans and AI collaborators.

## Code of Conduct

Be excellent to each other. We're SQUID pirates, not trolls.

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow
- Have fun and embrace the spirit of open source

## How to Contribute

### Reporting Bugs 🐛

Found a bug? Help us squash it:

1. **Check existing issues** - Someone might have already reported it
2. **Create a detailed bug report** including:
   - Clear description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (Python version, OS, etc.)
   - Error messages or logs
   - Screenshots if applicable

### Suggesting Features 💡

Have an idea for a new feature?

1. **Open an issue** with the `enhancement` label
2. **Describe the feature** and why it would be useful
3. **Consider the scope** - Does it fit the project's goals?
4. **Be open to discussion** - Others might have insights or alternatives

### Pull Requests 🚀

Ready to contribute code? Here's the workflow:

#### 1. Setup Your Environment

```bash
# Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/squid-digest.git
cd squid-digest

# Create virtual environment
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Copy environment template
cp env.template .env
# Add your API keys to .env (never commit this file!)
```

#### 2. Create a Branch

```bash
# Create a descriptive branch name
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-you-are-fixing
```

#### 3. Make Your Changes

Follow these guidelines:

**Code Style:**
- Follow PEP 8 Python style guide
- Use type hints where appropriate
- Write docstrings for functions and classes
- Keep functions focused and small
- Use meaningful variable names

**Testing:**
- Add tests for new features
- Ensure existing tests pass
- Run the test suite: `python scripts/run_all_tests.py`
- Aim for good test coverage

**Documentation:**
- Update README.md if needed
- Add docstrings to new functions
- Update relevant .md files
- Include examples for new features

#### 4. Test Your Changes

```bash
# Run all tests
python scripts/run_all_tests.py

# Run specific test
pytest tests/test_your_feature.py -v

# Run pre-commit hooks
pre-commit run --all-files
```

#### 5. Commit Your Changes

```bash
# Stage your changes
git add .

# Commit with a clear message
git commit -m "feat: Add awesome new feature"
# or
git commit -m "fix: Resolve bug in digest generation"
```

**Commit Message Format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions or changes
- `refactor:` - Code refactoring
- `style:` - Code style changes (formatting, etc.)
- `chore:` - Maintenance tasks

#### 6. Push and Create PR

```bash
# Push to your fork
git push origin feature/your-feature-name

# Go to GitHub and create a Pull Request
```

**PR Description Should Include:**
- What changes you made and why
- How to test the changes
- Any breaking changes
- Screenshots (if UI-related)
- Link to related issues

### Pre-commit Hooks

We use pre-commit hooks to maintain code quality:

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Hooks will run automatically on commit
# Or run manually:
pre-commit run --all-files
```

Hooks check for:
- Python syntax errors (ruff)
- Test failures
- File validation

## Security Guidelines 🔒

**Critical**: Before submitting any PR, ensure:

1. **No Hardcoded Secrets** - Never commit API keys, passwords, or tokens
2. **Use Environment Variables** - All credentials must use `os.getenv()` or similar
3. **Check .gitignore** - Verify sensitive files are properly excluded
4. **Review Git History** - Use `git log -p` to check what you're committing
5. **Test Locally** - Verify your changes work with environment variables

**Security Checklist**:
- [ ] No API keys in code
- [ ] No secrets in commit messages
- [ ] `.env` files not tracked
- [ ] No credentials in logs or error messages
- [ ] All secrets use environment variables

See [Security Policy](docs/SECURITY.md) and [Security Audit](docs/SECURITY_AUDIT.md) for more details.

## AI-Assisted Contributions 🤖

We embrace AI-assisted development! If you used AI tools to help with your contribution:

1. **Review the code yourself** - Ensure you understand what it does
2. **Test thoroughly** - AI can make mistakes
3. **Check for security issues** - Never commit secrets or credentials
4. **Mention it in your PR** - "Implemented with assistance from Claude/ChatGPT/Cursor"
5. **Take ownership** - You're responsible for the code you submit

## Project Structure

```
squid-digest/
├── src/squid_digest/          # Main source code
│   ├── core/                  # Business logic
│   ├── llm/                   # LLM providers
│   ├── tools/                 # API clients
│   ├── email/                 # Ghost email integration
│   ├── telegram/              # Telegram integration
│   └── context/               # Prompts and templates
├── scripts/                   # Utility scripts
├── tests/                     # Test suite
├── .github/workflows/         # GitHub Actions
└── writeup/                   # Generated digests
```

## Development Tips

### Running Locally

```bash
# Generate a test digest
python scripts/digest.py

# Test email sending (dry run)
python scripts/send_email.py --type public --digest-file writeup/2025/11/20/signals_2025-11-20.md --dry-run

# Run specific tests
pytest tests/test_email.py -v
```

### Adding a New LLM Provider

1. Add provider to `src/squid_digest/llm/providers.py`
2. Implement the required interface
3. Add tests in `tests/`
4. Update documentation
5. Add provider to `LLM_CHAT_PROVIDER` options in env.template

### Adding New Features

1. **Start small** - Break down into manageable pieces
2. **Write tests first** - TDD helps clarify requirements
3. **Update docs** - Keep README and other docs in sync
4. **Ask questions** - Open an issue if you're unsure about approach

## Getting Help

- **Questions?** Open an issue with the `question` label
- **Stuck?** Describe what you've tried in an issue
- **Need direction?** Check existing issues or create a discussion

## Recognition

Contributors will be recognized in:
- GitHub contributors list
- Release notes for significant contributions
- Project documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Remember**: Every contribution, no matter how small, makes this project better. Whether you're fixing a typo, adding a feature, or improving docs—thank you for being part of Squid Digest! 🦑🏴‍☠️
