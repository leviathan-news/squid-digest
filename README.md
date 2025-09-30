# squid-digest

Tiny Django starter for Leviathan News daily digest.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py runserver
```

# Config
.env controls:
* TIME_ZONE
* DJANGO_DEBUG
* DJANGO_ALLOWED_HOSTS
* DJANGO_SECRET_KEY
