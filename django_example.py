"""
Example: Adding Django web app on top of the existing CLI tool.

This shows how you'd integrate Django while keeping the CLI independent.
Your existing service/client code remains unchanged.

Directory structure would be:

squid-digest/
├── src/digest/              # Your existing CLI tool (unchanged)
│   ├── cli.py
│   ├── config.py
│   ├── clients/
│   └── services/
├── web/                     # New Django app (separate)
│   ├── manage.py
│   ├── config/              # Django settings
│   │   ├── settings.py
│   │   └── urls.py
│   └── digest_web/          # Django app
│       ├── views.py
│       └── urls.py
└── pyproject.toml           # Add django as optional dependency

"""

# ============================================================================
# web/digest_web/views.py - Django views reusing your existing code
# ============================================================================

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

# Import your existing service layer (no changes needed!)
from digest.clients import LeviathanNewsClient, PerplexityClient, GhostClient
from digest.services import DigestService
from digest.config import config


@require_http_methods(["POST"])
@csrf_exempt
def generate_digest(request):
    """
    API endpoint to generate digest.
    POST /api/digest/?limit=10&dry_run=true
    """
    try:
        limit = int(request.GET.get('limit', 10))
        dry_run = request.GET.get('dry_run', 'false').lower() == 'true'

        # Reuse existing clients and service (no changes needed!)
        leviathan = LeviathanNewsClient()
        perplexity = PerplexityClient(api_key=config.PERPLEXITY_API_KEY)
        ghost = GhostClient(
            ghost_url=config.GHOST_URL,
            admin_api_key=config.GHOST_ADMIN_API_KEY
        )

        service = DigestService(leviathan, perplexity, ghost)

        # Fetch and generate
        news_items = service.fetch_news(limit=limit)
        digest_content = service.generate_digest(news_items)

        # Publish if not dry run
        if not dry_run:
            service.publish_digest(digest_content)

        return JsonResponse({
            'status': 'success',
            'content': digest_content,
            'dry_run': dry_run,
            'items_processed': len(news_items)
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint."""
    return JsonResponse({'status': 'ok'})


# ============================================================================
# web/digest_web/urls.py - Django URL routing
# ============================================================================

from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('api/digest/', views.generate_digest, name='generate_digest'),
]


# ============================================================================
# web/config/settings.py - Django settings
# ============================================================================

"""
Minimal Django settings - most config stays in digest.config.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'digest_web',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

# No database needed if you're just running CLI tasks via API
DATABASES = {}


# ============================================================================
# pyproject.toml - Add Django as optional dependency
# ============================================================================

"""
[project]
name = "squid-digest"
version = "0.1.0"
description = "AI-powered daily news digest generator"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
    "pytest>=8.4.2",
]

[project.optional-dependencies]
web = [
    "django>=5.0.0",
    "gunicorn>=21.0.0",  # For production
]

[project.scripts]
digest-news = "digest.cli:main"


# Install with web support:
# uv sync --extra web
# or: uv pip install -e ".[web]"
"""


# ============================================================================
# Usage
# ============================================================================

"""
# CLI stays independent (works without Django)
$ uv run digest-news --limit 10

# Install with web support
$ uv sync --extra web

# Run Django dev server
$ cd web && python manage.py runserver

# Call via HTTP
$ curl -X POST "http://localhost:8000/api/digest/?limit=10&dry_run=true"

# Deploy to production
$ cd web && gunicorn config.wsgi:application
"""


# ============================================================================
# Key Points
# ============================================================================

"""
✓ CLI and web are separate entry points
✓ They both import the same service/client code
✓ No changes to existing digest.services or digest.clients
✓ Django is optional dependency (CLI works without it)
✓ Can deploy CLI and web app independently
✓ Service layer is framework-agnostic (works with Django, FastAPI, Flask, etc.)

This is much cleaner than having Django be the only interface!
"""
