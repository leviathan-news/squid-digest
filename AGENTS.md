# Repository Guidelines

## Project Structure & Module Organization

- `src/squid_digest/`: Primary Python package (core digest engine, backtesting, LLM providers, email/telegram formatting, RSS utilities).
- `config/` + `manage.py`: Django configuration and entry point for management commands.
- `scripts/`: Operational scripts used by automation (e.g., digest generation, README/writeup updates, security checks).
- `tests/`: Pytest suite and helper runners (`tests/README.md` explains what’s covered).
- `docs/`: Architecture, usage, security policy, and setup guides.
- `writeup/`: Generated daily outputs/archives (often updated by automation; avoid large rewrites unless intentional).

## Build, Test, and Development Commands

This repo uses `uv` for dependency management.

- `uv sync`: Install dependencies from `pyproject.toml`/`uv.lock`.
- `uv run python manage.py help`: List available Django commands; use `uv run python manage.py <command> --help` for options.
- `uv run python scripts/digest.py --help`: Run the standalone digest script (and inspect flags).
- `uv run pytest tests/ -v`: Run the test suite with verbose output.
- `uv run python scripts/run_all_tests.py`: Project’s “run everything” test runner (matches pre-commit behavior).
- `pre-commit install` / `pre-commit run --all-files`: Run hooks (syntax checks + tests + validations).

## Coding Style & Naming Conventions

- Python 3.11+, 4-space indentation, and PEP 8 conventions.
- Prefer type hints and small, single-purpose functions (follow patterns in `src/squid_digest/`).
- Names: `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.

## Testing Guidelines

- Use `pytest`; test files live in `tests/` and follow `test_*.py`.
- When changing output formatting (email/telegram/markdown), add/adjust snapshot-like assertions in the relevant test module.

## Commit & Pull Request Guidelines

- Commit messages commonly use Conventional Commit prefixes (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`); emoji prefixes are used in automated daily updates.
- PRs should include: what/why, how to test (exact commands), and any config/env changes (never include secrets).

## Security & Configuration Tips

- Keep secrets in local `.env` (gitignored) created from `env.template`; never commit credentials or tokens.
- If your change touches auth/publishing/integrations, skim `docs/SECURITY.md` and run `uv run python scripts/security_scan.py`.
