# 4000 Essential Words — Bot + Web App

Telegram bot + Django web app for learning the *4000 Essential English Words*.
See `docs/superpowers/specs/` for the product vision and phase specs.

## Stack
Python 3.13 · Django 6 · uv · PostgreSQL · Redis · Celery · django-unfold · Docker Compose.

## Local development

```bash
# 1. Install deps (uv)
python -m pip install --user uv
uv sync

# 2. Config
cp .env.example .env

# 3. Infra
docker compose up -d db redis

# 4. Migrate + create admin
uv run python manage.py migrate
uv run python manage.py createsuperuser   # phone like 998901234567

# 5. Import content (~4000 words + images)
uv run python manage.py import_words
uv run python manage.py sync_audio         # optional; native mp3 + gTTS fallback

# 6. Run
uv run python manage.py runserver
```

Admin: http://localhost:8000/admin/

## Full stack (Docker)

```bash
docker compose up --build
docker compose exec web python manage.py import_words
```

## Tests

```bash
docker compose up -d db redis
uv run pytest
uv run ruff check .
```
