# Faza 0 — Poydevor (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modernize the project (Django 6 async-first, uv, Postgres, Redis, Celery, Docker, django-unfold), restructure into `config/` + `apps/`, redesign content models (Book→Unit→Word), and build an idempotent import + audio pipeline that loads all ~4000 words with images and audio, browsable in the admin.

**Architecture:** Monorepo Django project. `config/` holds split settings (base/dev/prod) driven by env vars. `apps/common`, `apps/catalog`, `apps/accounts` hold domain code. Content is loaded by a custom `import_words` management command reading the existing `data/book{n}.json` dumpdata fixtures (source of truth for Uzbek translations) and linking the 3600 pre-existing images; audio is synced separately. Everything runs under Docker Compose (db, redis, web, worker, beat, bot-stub).

**Tech Stack:** Python 3.13 · Django 6.0 · uv · PostgreSQL 16 · Redis 7 · Celery 5 + Beat · django-unfold · psycopg3 · Pillow · gTTS · pytest + pytest-django · ruff · Docker Compose.

## Global Constraints

- **Python:** 3.13 (Docker image `python:3.13-slim`; Django 6.0 requires 3.12+).
- **Django:** `>=6.0,<6.1`.
- **Dependency manager:** `uv` with `pyproject.toml` + `uv.lock`. Never edit a `requirements.txt`; it is removed.
- **Settings module:** `config.settings.dev` for local/dev, `config.settings.prod` for production, selected via `DJANGO_SETTINGS_MODULE`.
- **App import paths / labels:** `apps.common` (label `common`), `apps.catalog` (label `catalog`), `apps.accounts` (label `accounts`). `AUTH_USER_MODEL = "accounts.User"`.
- **Media:** `MEDIA_ROOT = BASE_DIR / "media"`; word images at `images/words/{book}/{unit}/{en}.jpg`, audio at `audio/words/{book}/{unit}/{en}.mp3`.
- **Timezone:** `TIME_ZONE = "Asia/Tashkent"`, `USE_TZ = True`. i18n: `LANGUAGE_CODE = "uz"`, `LANGUAGES = [("uz",...),("en",...)]`.
- **UI language:** Uzbek primary, i18n-ready.
- **Data source of truth:** local `data/book1-6.json` for `uz` translations; remote `essentialenglish.review` only for native audio. Import merges by `en`.
- **No secrets in code:** `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL`, `BOT_TOKEN`, `TTS_PROVIDER` come from env.
- **Out of scope (do NOT build):** bot handlers/onboarding, scheduling logic, learning/SRS, quizzes, group quiz, roles/guardianship, web pages, games.
- **Commit style:** small commits per task; message footer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

### Prerequisite (once, before Task 1)

Create an isolated branch for this work:

```bash
git checkout -b phase-0-foundation
```

All tasks run in the repo root `D:\Projects\Personal\english_quiz`. Bash examples use POSIX paths; on Windows PowerShell adjust as needed.

---

### Task 1: Tooling — uv, pyproject, ruff, pytest

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Delete: `requirements.txt`

**Interfaces:**
- Produces: a working `uv` environment where `uv run python`, `uv run pytest`, `uv run ruff` all function; project deps (`django`, `celery`, `psycopg`, `django-unfold`, `django-environ`, `pillow`, `gtts`, `redis`, `requests`, `aiogram`) installed.

- [ ] **Step 1: Install uv** (uv is not present on this machine)

Run:
```bash
python -m pip install --user uv
uv --version
```
Expected: prints a uv version (e.g. `uv 0.9.x`). If `uv` is not on PATH, use `python -m uv` in place of `uv` for subsequent commands.

- [ ] **Step 2: Create `.python-version`**

```
3.13
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "english-quiz"
version = "0.1.0"
description = "4000 Essential Words — Telegram bot + web app"
requires-python = ">=3.13"
dependencies = [
    "django>=6.0,<6.1",
    "django-environ>=0.11",
    "django-unfold>=0.43",
    "psycopg[binary]>=3.2",
    "redis>=5.2",
    "celery[redis]>=5.4",
    "django-celery-beat>=2.7",
    "pillow>=11.0",
    "gtts>=2.5",
    "requests>=2.32",
    "whitenoise>=6.8",
    "gunicorn>=23.0",
    "uvicorn>=0.34",
    "aiogram>=3.15",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-django>=4.9",
    "pytest-cov>=6.0",
    "factory-boy>=3.3",
    "ruff>=0.9",
    "pre-commit>=4.0",
]

[tool.ruff]
line-length = 100
target-version = "py313"
extend-exclude = ["migrations"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "DJ"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.dev"
python_files = ["test_*.py", "tests.py"]
addopts = "-ra"

[tool.uv]
package = false
```

- [ ] **Step 4: Delete `requirements.txt` and sync the environment**

Run:
```bash
rm requirements.txt
uv sync
```
Expected: uv creates `.venv/` and `uv.lock`, installs Django 6.0 and all deps without error.

- [ ] **Step 5: Verify the toolchain**

Run:
```bash
uv run python -c "import django; print(django.get_version())"
uv run ruff --version
uv run pytest --version
```
Expected: Django prints `6.0.x`; ruff and pytest print their versions.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .python-version
git rm --cached requirements.txt 2>/dev/null; git add -A
git commit -m "build: switch to uv + pyproject with Django 6, ruff, pytest"
```

---

### Task 2: Project skeleton & Docker infra (config/, apps/, settings, compose db+redis)

**Files:**
- Move: `src/` → `config/` (then split settings)
- Move: `words/` → `apps/catalog/`, `accounts/` → `apps/accounts/`, `uploads/` → `media/`
- Create: `apps/__init__.py`, `apps/common/__init__.py`, `apps/common/apps.py`, `apps/common/models.py`
- Create: `config/settings/__init__.py`, `config/settings/base.py`, `config/settings/dev.py`, `config/settings/prod.py`
- Create: `config/celery.py`
- Modify: `config/__init__.py`, `config/urls.py`, `config/asgi.py`, `config/wsgi.py`, `manage.py`
- Modify: `apps/catalog/apps.py`, `apps/accounts/apps.py`
- Delete: `accounts/migrations/0001_initial.py`, `words/migrations/0001_initial.py` (regenerated later)
- Create: `Dockerfile`, `compose.yaml`, `.dockerignore`, `.env.example`, `.env`

**Interfaces:**
- Produces: `manage.py check` passes on `config.settings.dev`; `docker compose up -d db redis` yields healthy Postgres 16 + Redis 7; `TimeStampedModel` abstract base at `apps.common.models.TimeStampedModel` (fields `created_at`, `updated_at`).
- Note: existing `words`/`accounts` model bodies are relocated **unchanged** in this task (so `check` stays green with zero migrations). Their redesign happens in Tasks 3–4.

- [ ] **Step 1: Relocate directories**

Run:
```bash
mkdir -p apps
git mv src config
git mv words apps/catalog
git mv accounts apps/accounts
git mv uploads media
touch apps/__init__.py
```

- [ ] **Step 2: Fix moved app configs**

`apps/catalog/apps.py`:
```python
from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"
    label = "catalog"
    verbose_name = "Catalog"
```

`apps/accounts/apps.py`:
```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"
```

- [ ] **Step 3: Create `apps/common` with `TimeStampedModel`**

`apps/common/__init__.py`: (empty file)

`apps/common/apps.py`:
```python
from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"
    label = "common"
```

`apps/common/models.py`:
```python
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base adding self-managed created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

- [ ] **Step 4: Delete stale migrations (fresh start, no prod data)**

Run:
```bash
rm apps/accounts/migrations/0001_initial.py apps/catalog/migrations/0001_initial.py
```
(Keep the `__init__.py` files in each `migrations/` dir.)

- [ ] **Step 5: Split settings**

`config/settings/__init__.py`: (empty file)

`config/settings/base.py`:
```python
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["*"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    # local
    "apps.common",
    "apps.accounts",
    "apps.catalog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL", default="sqlite:///" + str(BASE_DIR / "db.sqlite3"))}

CACHES = {"default": env.cache("REDIS_URL", default="locmemcache://")}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
LANGUAGES = [("uz", "O'zbekcha"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=env("REDIS_URL", default="redis://localhost:6379/0"))
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Pluggable TTS
TTS_PROVIDER = env("TTS_PROVIDER", default="apps.common.tts.GTTSProvider")

# Telegram (Phase 1+)
BOT_TOKEN = env("BOT_TOKEN", default="")

UNFOLD = {
    "SITE_TITLE": "4000 Essential Words",
    "SITE_HEADER": "4000 Essential Words",
    "SITE_SYMBOL": "school",
}
```

`config/settings/dev.py`:
```python
from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
```

`config/settings/prod.py`:
```python
from .base import *  # noqa: F403

DEBUG = False
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

- [ ] **Step 6: Point entrypoints at `config`**

`manage.py` — change the settings default:
```python
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
```

`config/asgi.py`:
```python
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
application = get_asgi_application()
```

`config/wsgi.py`:
```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
application = get_wsgi_application()
```

`config/__init__.py`:
```python
from .celery import app as celery_app

__all__ = ("celery_app",)
```

`config/urls.py`:
```python
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

- [ ] **Step 7: Celery app**

`config/celery.py`:
```python
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("english_quiz")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

- [ ] **Step 8: Env files**

`.env.example`:
```dotenv
SECRET_KEY=dev-insecure-change-me
DEBUG=True
ALLOWED_HOSTS=*
DATABASE_URL=postgres://postgres:postgres@localhost:5432/english_quiz
REDIS_URL=redis://localhost:6379/1
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
TTS_PROVIDER=apps.common.tts.GTTSProvider
BOT_TOKEN=
```

Create `.env` as a copy:
```bash
cp .env.example .env
```

- [ ] **Step 9: Docker files**

`.dockerignore`:
```
.git
.venv
__pycache__
*.pyc
db.sqlite3
.env
staticfiles
docs
```

`Dockerfile`:
```dockerfile
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "config.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

`scripts/entrypoint.sh`:
```bash
#!/usr/bin/env bash
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi
if [ "${COLLECT_STATIC:-0}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
```
Then: `chmod +x scripts/entrypoint.sh`

`compose.yaml`:
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: english_quiz
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  web:
    build: .
    env_file: .env
    environment:
      DATABASE_URL: postgres://postgres:postgres@db:5432/english_quiz
      REDIS_URL: redis://redis:6379/1
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      COLLECT_STATIC: "1"
    volumes:
      - ./media:/app/media
    ports:
      - "8000:8000"
    depends_on:
      db: {condition: service_healthy}
      redis: {condition: service_healthy}

  worker:
    build: .
    command: celery -A config worker -l info
    env_file: .env
    environment:
      DATABASE_URL: postgres://postgres:postgres@db:5432/english_quiz
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
      RUN_MIGRATIONS: "0"
    volumes:
      - ./media:/app/media
    depends_on:
      db: {condition: service_healthy}
      redis: {condition: service_healthy}

  beat:
    build: .
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    env_file: .env
    environment:
      DATABASE_URL: postgres://postgres:postgres@db:5432/english_quiz
      CELERY_BROKER_URL: redis://redis:6379/0
      RUN_MIGRATIONS: "0"
    depends_on:
      db: {condition: service_healthy}
      redis: {condition: service_healthy}

volumes:
  pgdata:
```
(The `bot` service is added in Task 10 once a stub exists.)

- [ ] **Step 10: Bring up infra and verify Django boots**

Run:
```bash
docker compose up -d db redis
uv run python manage.py check
```
Expected: compose reports `db` and `redis` healthy; `manage.py check` prints `System check identified no issues (0 silenced).`

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "refactor: restructure into config/ + apps/, split settings, add Docker db+redis, Celery app"
```

---

### Task 3: Accounts models — phone optional + TelegramAccount

**Files:**
- Modify: `apps/accounts/models.py`
- Modify: `apps/accounts/managers.py`
- Create: `apps/accounts/tests/__init__.py`, `apps/accounts/tests/test_models.py`
- Create (generated): `apps/accounts/migrations/0001_initial.py`

**Interfaces:**
- Produces: `accounts.User` (phone `null=True, blank=True, unique`; `USERNAME_FIELD="phone_number"`; `full_name` property); `accounts.TelegramAccount` (OneToOne `user`, `telegram_id` unique BigInt, plus profile fields). `User.objects.create_user(first_name, phone_number, password)` still works for superusers.

- [ ] **Step 1: Write the failing tests**

`apps/accounts/tests/__init__.py`: (empty file)

`apps/accounts/tests/test_models.py`:
```python
import pytest

from apps.accounts.models import TelegramAccount, User

pytestmark = pytest.mark.django_db


def test_user_can_be_created_without_phone():
    user = User.objects.create(first_name="Ali")
    assert user.phone_number is None
    assert user.full_name == "Ali"


def test_full_name_includes_last_name():
    user = User.objects.create(first_name="Ali", last_name="Valiyev")
    assert user.full_name == "Ali Valiyev"


def test_create_user_manager_requires_phone():
    with pytest.raises(ValueError):
        User.objects.create_user(first_name="Ali", phone_number=None, password="x")


def test_telegram_account_links_to_user():
    user = User.objects.create(first_name="Ali")
    tg = TelegramAccount.objects.create(user=user, telegram_id=12345, username="ali")
    assert user.telegram.telegram_id == 12345
    assert str(tg) == "@ali"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest apps/accounts/tests/test_models.py -v`
Expected: FAIL — `TelegramAccount` does not exist / phone not nullable.

- [ ] **Step 3: Update the models**

`apps/accounts/models.py`:
```python
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel

from .managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length=100, verbose_name=_("Name"))
    last_name = models.CharField(max_length=100, blank=True, default="", verbose_name=_("Surname"))
    phone_number = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        verbose_name=_("Phone number"),
        validators=[
            RegexValidator(regex=r"^998(90|91|93|94|95|97|98|99|33|88|77|20)[0-9]{7}$"),
        ],
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["first_name"]

    objects = CustomUserManager()

    class Meta:
        db_table = "users"
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        if self.phone_number:
            return f"{self.full_name} +{self.phone_number}"
        return self.full_name or str(self.pk)


class TelegramAccount(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="telegram")
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=64, blank=True, default="")
    first_name = models.CharField(max_length=128, blank=True, default="")
    last_name = models.CharField(max_length=128, blank=True, default="")
    language_code = models.CharField(max_length=8, blank=True, default="")
    is_premium = models.BooleanField(default=False)
    blocked_bot = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Telegram account")
        verbose_name_plural = _("Telegram accounts")

    def __str__(self) -> str:
        return f"@{self.username}" if self.username else str(self.telegram_id)
```

- [ ] **Step 4: Keep the manager compatible**

Verify `apps/accounts/managers.py` still raises `ValueError` when `phone_number` is falsy (the existing `create_user` already does). No change needed unless it imports the wrong base; ensure the top imports are:
```python
from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _
```
(Remove the unused `AbstractBaseUser` import and `Union` if present; use `str | int` type hints.)

- [ ] **Step 5: Make migrations and run tests**

Run:
```bash
uv run python manage.py makemigrations accounts
uv run pytest apps/accounts/tests/test_models.py -v
```
Expected: migration `0001_initial` created; all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/accounts
git commit -m "feat(accounts): optional phone, add TelegramAccount model"
```

---

### Task 4: Catalog models — Book, Unit, Word + pronunciation parsing

**Files:**
- Modify: `apps/catalog/models.py`
- Delete: `apps/catalog/utils.py` (its `speach` moves to `apps/common/tts.py` in Task 5; remove the import now)
- Create: `apps/catalog/tests/__init__.py`, `apps/catalog/tests/test_models.py`
- Create (generated): `apps/catalog/migrations/0001_initial.py`

**Interfaces:**
- Produces:
  - `catalog.Book(number unique, title, slug unique, description, level, cover, pdf, word_count, is_active)`
  - `catalog.Unit(book FK related_name="units", number, title, slug, word_count)` unique `(book, number)`
  - `catalog.Word(unit FK related_name="words", order, en, uz, part_of_speech, pronunciation, definition, example, image, audio_en, audio_uz)` unique `(unit, en)`, `.book` property
  - `catalog.models.parse_pronunciation(raw: str | None) -> tuple[str, str]` returning `(ipa, part_of_speech)`

- [ ] **Step 1: Write the failing tests**

`apps/catalog/tests/__init__.py`: (empty file)

`apps/catalog/tests/test_models.py`:
```python
import pytest
from django.db import IntegrityError

from apps.catalog.models import Book, Unit, Word, parse_pronunciation

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("[əˈfreid] adj.", ("[əˈfreid]", "adj.")),
        ("[əˈɡriː] v.", ("[əˈɡriː]", "v.")),
        ("n.", ("", "n.")),
        ("", ("", "")),
        (None, ("", "")),
    ],
)
def test_parse_pronunciation(raw, expected):
    assert parse_pronunciation(raw) == expected


def test_word_book_property_and_str():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="qo'rqib", order=1)
    assert word.book == book
    assert str(word) == "afraid — qo'rqib"


def test_unit_unique_per_book():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    Unit.objects.create(book=book, number=1)
    with pytest.raises(IntegrityError):
        Unit.objects.create(book=book, number=1)


def test_word_unique_per_unit():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    unit = Unit.objects.create(book=book, number=1)
    Word.objects.create(unit=unit, en="afraid", uz="a")
    with pytest.raises(IntegrityError):
        Word.objects.create(unit=unit, en="afraid", uz="b")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest apps/catalog/tests/test_models.py -v`
Expected: FAIL — new model shape / `parse_pronunciation` not present.

- [ ] **Step 3: Rewrite `apps/catalog/models.py`**

```python
from __future__ import annotations

import re

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel

_PRON_RE = re.compile(r"^\s*(\[[^\]]*\])?\s*(.*?)\s*$")


def parse_pronunciation(raw: str | None) -> tuple[str, str]:
    """Split e.g. '[əˈfreid] adj.' into ('[əˈfreid]', 'adj.')."""
    if not raw:
        return ("", "")
    match = _PRON_RE.match(raw)
    if not match:
        return ("", raw.strip())
    ipa = (match.group(1) or "").strip()
    pos = (match.group(2) or "").strip()
    return (ipa, pos)


class Book(TimeStampedModel):
    number = models.PositiveSmallIntegerField(unique=True, verbose_name=_("Number"))
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=8, blank=True)
    cover = models.ImageField(upload_to="images/books/covers/", blank=True, null=True)
    pdf = models.FileField(upload_to="books/pdf/", blank=True, null=True)
    word_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("number",)
        verbose_name = _("Book")
        verbose_name_plural = _("Books")

    def __str__(self) -> str:
        return self.title


class Unit(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="units")
    number = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=200, blank=True)
    word_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("book", "number")
        constraints = [models.UniqueConstraint(fields=["book", "number"], name="uniq_book_unit")]
        verbose_name = _("Unit")
        verbose_name_plural = _("Units")

    def __str__(self) -> str:
        return f"{self.book.title} — Unit {self.number}"


def word_image_upload_to(instance: "Word", filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1]
    return f"images/words/{instance.unit.book.number}/{instance.unit.number}/{instance.en}.{ext}"


def word_audio_upload_to(instance: "Word", filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1]
    return f"audio/words/{instance.unit.book.number}/{instance.unit.number}/{instance.en}.{ext}"


class Word(TimeStampedModel):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="words")
    order = models.PositiveSmallIntegerField(default=0)
    en = models.CharField(max_length=100, verbose_name=_("English"))
    uz = models.CharField(max_length=255, verbose_name=_("Uzbek"))
    part_of_speech = models.CharField(max_length=20, blank=True)
    pronunciation = models.CharField(max_length=100, blank=True)
    definition = models.TextField(blank=True)
    example = models.TextField(blank=True)
    image = models.ImageField(upload_to=word_image_upload_to, blank=True, null=True)
    audio_en = models.FileField(upload_to=word_audio_upload_to, blank=True, null=True)
    audio_uz = models.FileField(upload_to=word_audio_upload_to, blank=True, null=True)

    class Meta:
        ordering = ("unit", "order")
        constraints = [models.UniqueConstraint(fields=["unit", "en"], name="uniq_unit_word")]
        indexes = [models.Index(fields=["en"])]
        verbose_name = _("Word")
        verbose_name_plural = _("Words")

    @property
    def book(self) -> Book:
        return self.unit.book

    def __str__(self) -> str:
        return f"{self.en} — {self.uz}"
```

- [ ] **Step 4: Make migrations and run tests**

Run:
```bash
uv run python manage.py makemigrations catalog
uv run pytest apps/catalog/tests/test_models.py -v
```
Expected: migration created; all tests PASS.

- [ ] **Step 5: Apply the full schema to Postgres**

Run: `uv run python manage.py migrate`
Expected: all migrations (accounts, catalog, admin, auth, django_celery_beat, …) apply cleanly to the Dockerized Postgres.

- [ ] **Step 6: Commit**

```bash
git add apps/catalog
git commit -m "feat(catalog): redesign Book/Unit/Word models with pronunciation parsing"
```

---

### Task 5: Pluggable TTS abstraction

**Files:**
- Create: `apps/common/tts.py`
- Create: `apps/common/tests/__init__.py`, `apps/common/tests/test_tts.py`

**Interfaces:**
- Produces: `apps.common.tts.TTSProvider` (abstract `synthesize(text, lang="en") -> bytes`), `GTTSProvider`, and `get_tts_provider()` which resolves `settings.TTS_PROVIDER` to an instance.

- [ ] **Step 1: Write the failing test**

`apps/common/tests/__init__.py`: (empty file)

`apps/common/tests/test_tts.py`:
```python
from unittest.mock import MagicMock, patch

from apps.common.tts import GTTSProvider, TTSProvider, get_tts_provider


def test_get_tts_provider_returns_configured_instance(settings):
    settings.TTS_PROVIDER = "apps.common.tts.GTTSProvider"
    provider = get_tts_provider()
    assert isinstance(provider, GTTSProvider)
    assert isinstance(provider, TTSProvider)


@patch("apps.common.tts.gTTS")
def test_gtts_provider_synthesizes_bytes(mock_gtts):
    def fake_write(fp):
        fp.write(b"ID3-audio")

    instance = MagicMock()
    instance.write_to_fp.side_effect = fake_write
    mock_gtts.return_value = instance

    data = GTTSProvider().synthesize("hello", lang="en")
    assert data == b"ID3-audio"
    mock_gtts.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/common/tests/test_tts.py -v`
Expected: FAIL — module `apps.common.tts` not found.

- [ ] **Step 3: Implement `apps/common/tts.py`**

```python
from __future__ import annotations

from importlib import import_module
from io import BytesIO

from django.conf import settings
from gtts import gTTS


class TTSProvider:
    """Interface for text-to-speech backends returning MP3 bytes."""

    def synthesize(self, text: str, lang: str = "en") -> bytes:
        raise NotImplementedError


class GTTSProvider(TTSProvider):
    def __init__(self, tld: str = "co.uk", slow: bool = False) -> None:
        self.tld = tld
        self.slow = slow

    def synthesize(self, text: str, lang: str = "en") -> bytes:
        fp = BytesIO()
        tts = gTTS(text, lang=lang, slow=self.slow, tld=self.tld)
        tts.write_to_fp(fp)
        return fp.getvalue()


def get_tts_provider() -> TTSProvider:
    path = getattr(settings, "TTS_PROVIDER", "apps.common.tts.GTTSProvider")
    module_path, _, cls_name = path.rpartition(".")
    module = import_module(module_path)
    return getattr(module, cls_name)()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest apps/common/tests/test_tts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/common/tts.py apps/common/tests
git commit -m "feat(common): pluggable TTS provider abstraction (gTTS default)"
```

---

### Task 6: `import_words` management command (text + images)

**Files:**
- Create: `apps/catalog/management/__init__.py`, `apps/catalog/management/commands/__init__.py`, `apps/catalog/management/commands/import_words.py`
- Create: `apps/catalog/tests/test_import_words.py`

**Interfaces:**
- Consumes: `Book`, `Unit`, `Word`, `parse_pronunciation` from Task 4.
- Produces: `python manage.py import_words [--book N] [--dry-run] [--data-dir PATH]` — idempotent import from `data/book{n}.json` dumpdata fixtures; sets `pronunciation`/`part_of_speech` via `parse_pronunciation`; links existing images when the file exists under `MEDIA_ROOT`; updates `word_count` on Book and Unit.

- [ ] **Step 1: Write the failing test**

`apps/catalog/tests/test_import_words.py`:
```python
import json

import pytest
from django.core.management import call_command

from apps.catalog.models import Book, Unit, Word

pytestmark = pytest.mark.django_db

SAMPLE = [
    {
        "model": "words.word",
        "pk": 1,
        "fields": {
            "book": 1, "unit": 1, "en": "afraid", "uz": "qo'rqib",
            "definition": "feels fear", "example": "was <strong>afraid</strong>",
            "pronunciation": "[əˈfreid] adj.", "image": "images/words/1/1/afraid.jpg",
        },
    },
    {
        "model": "words.word",
        "pk": 2,
        "fields": {
            "book": 1, "unit": 1, "en": "agree", "uz": "rozi",
            "definition": "say yes", "example": "I <strong>agree</strong>",
            "pronunciation": "[əˈɡriː] v.", "image": "images/words/1/1/agree.jpg",
        },
    },
]


@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "book1.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    return tmp_path


def test_import_creates_book_unit_words(data_dir):
    call_command("import_words", "--book", "1", "--data-dir", str(data_dir))
    book = Book.objects.get(number=1)
    assert book.title == "4000 Essential English Words 1"
    assert book.word_count == 2
    unit = Unit.objects.get(book=book, number=1)
    assert unit.word_count == 2
    word = Word.objects.get(en="afraid")
    assert word.uz == "qo'rqib"
    assert word.pronunciation == "[əˈfreid]"
    assert word.part_of_speech == "adj."
    assert word.order == 1


def test_import_is_idempotent(data_dir):
    call_command("import_words", "--book", "1", "--data-dir", str(data_dir))
    call_command("import_words", "--book", "1", "--data-dir", str(data_dir))
    assert Word.objects.filter(en="afraid").count() == 1
    assert Book.objects.get(number=1).word_count == 2


def test_dry_run_writes_nothing(data_dir):
    call_command("import_words", "--book", "1", "--data-dir", str(data_dir), "--dry-run")
    assert Book.objects.count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/catalog/tests/test_import_words.py -v`
Expected: FAIL — `Unknown command: 'import_words'`.

- [ ] **Step 3: Implement the command**

Create the empty package files:
`apps/catalog/management/__init__.py`, `apps/catalog/management/commands/__init__.py` (both empty).

`apps/catalog/management/commands/import_words.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Book, Unit, Word, parse_pronunciation

BOOK_TITLE = "4000 Essential English Words {n}"


class Command(BaseCommand):
    help = "Import words from data/book{n}.json fixtures into Book/Unit/Word."

    def add_arguments(self, parser):
        parser.add_argument("--book", type=int, default=None, help="Import a single book number")
        parser.add_argument("--dry-run", action="store_true", help="Roll back at the end")
        parser.add_argument("--data-dir", type=str, default=str(settings.BASE_DIR / "data"))

    def handle(self, *args, **opts):
        data_dir = Path(opts["data_dir"])
        book_numbers = [opts["book"]] if opts["book"] else range(1, 7)
        for n in book_numbers:
            path = data_dir / f"book{n}.json"
            if not path.exists():
                self.stderr.write(self.style.WARNING(f"skip: {path} not found"))
                continue
            self._import_book(n, path, opts["dry_run"])

    def _import_book(self, n: int, path: Path, dry_run: bool) -> None:
        records = json.loads(path.read_text(encoding="utf-8"))
        with transaction.atomic():
            book, _ = Book.objects.update_or_create(
                number=n,
                defaults={"title": BOOK_TITLE.format(n=n), "slug": f"book-{n}"},
            )
            units: dict[int, Unit] = {}
            orders: dict[int, int] = {}
            for rec in records:
                f = rec["fields"]
                unit_no = f["unit"]
                unit = units.get(unit_no)
                if unit is None:
                    unit, _ = Unit.objects.update_or_create(
                        book=book,
                        number=unit_no,
                        defaults={
                            "title": f"Unit {unit_no}",
                            "slug": slugify(f"book-{n}-unit-{unit_no}"),
                        },
                    )
                    units[unit_no] = unit
                    orders[unit_no] = 0
                orders[unit_no] += 1
                ipa, pos = parse_pronunciation(f.get("pronunciation"))
                word, _ = Word.objects.update_or_create(
                    unit=unit,
                    en=f["en"],
                    defaults={
                        "uz": f.get("uz") or "",
                        "order": orders[unit_no],
                        "pronunciation": ipa[:100],
                        "part_of_speech": pos[:20],
                        "definition": f.get("definition") or "",
                        "example": f.get("example") or "",
                    },
                )
                image_rel = f.get("image")
                if image_rel and (Path(settings.MEDIA_ROOT) / image_rel).exists():
                    if word.image.name != image_rel:
                        word.image.name = image_rel
                        word.save(update_fields=["image"])
            for unit in units.values():
                unit.word_count = unit.words.count()
                unit.save(update_fields=["word_count"])
            book.word_count = Word.objects.filter(unit__book=book).count()
            book.save(update_fields=["word_count"])
            self.stdout.write(self.style.SUCCESS(f"book {n}: {book.word_count} words"))
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING(f"book {n}: dry-run rolled back"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest apps/catalog/tests/test_import_words.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 5: Real import smoke check**

Run: `uv run python manage.py import_words --book 1`
Expected: prints `book 1: <N> words` (N ≈ 600). Verify: `uv run python manage.py shell -c "from apps.catalog.models import Word; print(Word.objects.count())"`.

- [ ] **Step 6: Commit**

```bash
git add apps/catalog/management apps/catalog/tests/test_import_words.py
git commit -m "feat(catalog): import_words command (idempotent, links images)"
```

---

### Task 7: `sync_audio` management command (native mp3 + gTTS fallback)

**Files:**
- Create: `apps/catalog/management/commands/sync_audio.py`
- Create: `apps/catalog/tests/test_sync_audio.py`

**Interfaces:**
- Consumes: `Word` (Task 4), `get_tts_provider` (Task 5).
- Produces: `python manage.py sync_audio [--book N] [--source {remote,gtts}] [--overwrite]` — populates `Word.audio_en`. `--source remote` tries the source site's mp3 and falls back to gTTS on any failure; `--source gtts` always synthesizes. Idempotent: skips words that already have `audio_en` unless `--overwrite`.

- [ ] **Step 1: Write the failing test**

`apps/catalog/tests/test_sync_audio.py`:
```python
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.catalog.models import Book, Unit, Word

pytestmark = pytest.mark.django_db


@pytest.fixture
def word():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    unit = Unit.objects.create(book=book, number=1)
    return Word.objects.create(unit=unit, en="afraid", uz="a", order=1)


@patch("apps.catalog.management.commands.sync_audio.get_tts_provider")
def test_gtts_source_sets_audio(mock_get_provider, word):
    mock_get_provider.return_value.synthesize.return_value = b"ID3-audio"
    call_command("sync_audio", "--book", "1", "--source", "gtts")
    word.refresh_from_db()
    assert word.audio_en.name.endswith("afraid.mp3")
    assert word.audio_en.read() == b"ID3-audio"


@patch("apps.catalog.management.commands.sync_audio.get_tts_provider")
def test_skips_existing_without_overwrite(mock_get_provider, word):
    mock_get_provider.return_value.synthesize.return_value = b"one"
    call_command("sync_audio", "--book", "1", "--source", "gtts")
    mock_get_provider.return_value.synthesize.return_value = b"two"
    call_command("sync_audio", "--book", "1", "--source", "gtts")
    word.refresh_from_db()
    assert word.audio_en.read() == b"one"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/catalog/tests/test_sync_audio.py -v`
Expected: FAIL — `Unknown command: 'sync_audio'`.

- [ ] **Step 3: Implement the command**

`apps/catalog/management/commands/sync_audio.py`:
```python
from __future__ import annotations

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.catalog.models import Word
from apps.common.tts import get_tts_provider

REMOTE_MP3 = (
    "https://www.essentialenglish.review/apps-data/"
    "4000-essential-english-words-{book}/data/mp3/{name}.mp3"
)


class Command(BaseCommand):
    help = "Populate Word.audio_en from the source site's mp3 or via gTTS."

    def add_arguments(self, parser):
        parser.add_argument("--book", type=int, default=None)
        parser.add_argument("--source", choices=["remote", "gtts"], default="remote")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **opts):
        provider = get_tts_provider()
        qs = Word.objects.select_related("unit__book")
        if opts["book"]:
            qs = qs.filter(unit__book__number=opts["book"])
        if not opts["overwrite"]:
            qs = qs.filter(audio_en="")
        done = 0
        for word in qs.iterator():
            data = None
            if opts["source"] == "remote":
                data = self._fetch_remote(word)
            if data is None:
                data = provider.synthesize(word.en, lang="en")
            word.audio_en.save(f"{word.en}.mp3", ContentFile(data), save=True)
            done += 1
        self.stdout.write(self.style.SUCCESS(f"audio synced: {done} words"))

    def _fetch_remote(self, word: Word) -> bytes | None:
        url = REMOTE_MP3.format(book=word.unit.book.number, name=word.en)
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200 and resp.content:
                return resp.content
        except requests.RequestException as exc:
            self.stderr.write(self.style.WARNING(f"remote miss {word.en}: {exc}"))
        return None
```

> Note: the exact remote mp3 URL shape is unverified. If `--source remote` misses everything, the gTTS fallback still produces audio, so the command always succeeds. The `REMOTE_MP3` template is the single line to adjust once the real path is confirmed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest apps/catalog/tests/test_sync_audio.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/catalog/management/commands/sync_audio.py apps/catalog/tests/test_sync_audio.py
git commit -m "feat(catalog): sync_audio command (remote mp3 with gTTS fallback)"
```

---

### Task 8: django-unfold admin

**Files:**
- Modify: `apps/catalog/admin.py`
- Modify: `apps/accounts/admin.py`, `apps/accounts/forms.py`
- Create: `apps/catalog/tests/test_admin.py`

**Interfaces:**
- Consumes: models from Tasks 3–4.
- Produces: unfold-based admin — Books changelist with Units inline, Unit change with Words inline, Word changelist with image thumbnail + search/filter; User & TelegramAccount admin. A staff smoke test loads the Word changelist (HTTP 200).

- [ ] **Step 1: Write the failing test**

`apps/catalog/tests/test_admin.py`:
```python
import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    user = User.objects.create(first_name="Admin", phone_number=998900000000, is_staff=True, is_superuser=True)
    user.set_password("pw")
    user.save()
    client.force_login(user)
    return client


def test_word_changelist_loads(admin_client):
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    unit = Unit.objects.create(book=book, number=1)
    Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    resp = admin_client.get(reverse("admin:catalog_word_changelist"))
    assert resp.status_code == 200
    assert b"afraid" in resp.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/catalog/tests/test_admin.py -v`
Expected: FAIL — admin not registered for the redesigned models (or reverse/NoReverseMatch).

- [ ] **Step 3: Implement `apps/catalog/admin.py`**

```python
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .models import Book, Unit, Word


class UnitInline(TabularInline):
    model = Unit
    extra = 0
    fields = ("number", "title", "word_count")
    readonly_fields = ("word_count",)


class WordInline(TabularInline):
    model = Word
    extra = 0
    fields = ("order", "en", "uz", "part_of_speech")


@admin.register(Book)
class BookAdmin(ModelAdmin):
    list_display = ("number", "title", "level", "word_count", "is_active")
    search_fields = ("title",)
    inlines = (UnitInline,)


@admin.register(Unit)
class UnitAdmin(ModelAdmin):
    list_display = ("__str__", "book", "number", "word_count")
    list_filter = ("book",)
    inlines = (WordInline,)


@admin.register(Word)
class WordAdmin(ModelAdmin):
    list_display = ("en", "uz", "part_of_speech", "unit", "thumb")
    list_display_links = ("en",)
    list_filter = ("unit__book", "part_of_speech")
    search_fields = ("en", "uz")
    list_select_related = ("unit", "unit__book")

    @admin.display(description="image")
    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:36px;border-radius:4px" />', obj.image.url)
        return "—"
```

- [ ] **Step 4: Update `apps/accounts/admin.py` to unfold**

```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import TelegramAccount, User

admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    change_password_form = AdminPasswordChangeForm
    list_display = ("__str__", "first_name", "last_name", "phone_number", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active")
    search_fields = ("first_name", "last_name", "phone_number")
    ordering = ("id",)
    fieldsets = (
        (None, {"fields": ("first_name", "last_name", "phone_number", "password")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "is_active", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("first_name", "phone_number", "password1", "password2")}),
    )


@admin.register(TelegramAccount)
class TelegramAccountAdmin(ModelAdmin):
    list_display = ("telegram_id", "username", "user", "blocked_bot")
    search_fields = ("telegram_id", "username")
    raw_id_fields = ("user",)
```

Delete the now-unused `apps/accounts/forms.py` (unfold provides the forms) and remove any import of it:
```bash
git rm apps/accounts/forms.py
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest apps/catalog/tests/test_admin.py apps/accounts -v`
Expected: PASS (200, `afraid` present).

- [ ] **Step 6: Commit**

```bash
git add apps/catalog/admin.py apps/accounts/admin.py apps/catalog/tests/test_admin.py
git add -A
git commit -m "feat(admin): unfold admin for Book/Unit/Word/User/TelegramAccount"
```

---

### Task 9: Celery wiring — ping task

**Files:**
- Create: `apps/common/tasks.py`
- Create: `apps/common/tests/test_tasks.py`

**Interfaces:**
- Consumes: the Celery app from `config/celery.py` (Task 2).
- Produces: `apps.common.tasks.ping()` shared task returning `"pong"`, discoverable by the worker.

- [ ] **Step 1: Write the failing test**

`apps/common/tests/test_tasks.py`:
```python
from apps.common.tasks import ping


def test_ping_runs_eagerly(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    assert ping.apply().get() == "pong"


def test_ping_is_registered():
    from config.celery import app

    assert "apps.common.tasks.ping" in app.tasks
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/common/tests/test_tasks.py -v`
Expected: FAIL — `apps.common.tasks` not found.

- [ ] **Step 3: Implement `apps/common/tasks.py`**

```python
from celery import shared_task


@shared_task
def ping() -> str:
    """Trivial task used to verify worker + broker wiring."""
    return "pong"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest apps/common/tests/test_tasks.py -v`
Expected: PASS.

- [ ] **Step 5: Verify against a real worker (optional but recommended)**

Run (with `docker compose up -d db redis` still up):
```bash
uv run celery -A config worker -l info --pool solo &
uv run python -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev'); django.setup(); from apps.common.tasks import ping; print(ping.delay().get(timeout=10))"
```
Expected: prints `pong`. Then stop the worker (`kill %1` or Ctrl-C).

- [ ] **Step 6: Commit**

```bash
git add apps/common/tasks.py apps/common/tests/test_tasks.py
git commit -m "feat(common): ping task to verify Celery wiring"
```

---

### Task 10: Full stack compose (web/worker/beat/bot-stub) + entrypoint + docs

**Files:**
- Create: `bot/__init__.py`, `bot/__main__.py` (stub)
- Modify: `compose.yaml` (add `bot` service)
- Modify: `Readme.md`
- Verify: `scripts/entrypoint.sh` from Task 2

**Interfaces:**
- Produces: `docker compose up` starts db, redis, web (migrations + static + gunicorn/uvicorn on :8000), worker, beat, and a bot stub that stays alive without crashing; `Readme.md` documents setup, import, and run.

- [ ] **Step 1: Bot stub (keeps the `bot` service alive; real bot is Phase 1)**

`bot/__init__.py`: (empty file)

`bot/__main__.py`:
```python
"""Placeholder bot process for Phase 0.

Phase 1 replaces this with the aiogram dispatcher. For now it only
verifies the container builds and stays running.
"""

import time


def main() -> None:
    print("bot stub: Phase 0 placeholder — aiogram wiring lands in Phase 1", flush=True)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add the `bot` service to `compose.yaml`**

Add under `services:` (before `volumes:`):
```yaml
  bot:
    build: .
    command: python -m bot
    env_file: .env
    environment:
      DATABASE_URL: postgres://postgres:postgres@db:5432/english_quiz
      REDIS_URL: redis://redis:6379/1
      RUN_MIGRATIONS: "0"
    depends_on:
      db: {condition: service_healthy}
      redis: {condition: service_healthy}
```

- [ ] **Step 3: Rewrite `Readme.md`**

```markdown
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
```

- [ ] **Step 4: Verify the whole stack**

Run:
```bash
docker compose up --build -d
docker compose ps
docker compose exec web python manage.py import_words --book 1
```
Expected: all services `running`/`healthy`; `import_words` prints `book 1: <N> words`. Open http://localhost:8000/admin/ and confirm the Words changelist shows entries with thumbnails.

- [ ] **Step 5: Full test + lint gate**

Run:
```bash
uv run pytest
uv run ruff check .
```
Expected: all tests PASS; ruff reports no errors (fix any it flags).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: full docker compose (web/worker/beat/bot-stub) + entrypoint + docs"
```

---

## Self-Review (completed by plan author)

**Spec coverage** — every Phase 0 spec section maps to a task:
- §2 tech stack → Task 1 (uv/pyproject) + Task 2 (Docker/settings/celery)
- §3 repo structure → Task 2
- §4 content models → Task 4 (catalog) + Task 3 (accounts) + Task 2 (`TimeStampedModel`)
- §5 import pipeline → Task 6 (`import_words`) + Task 7 (`sync_audio`) + Task 5 (TTS)
- §6 settings → Task 2
- §7 Celery → Task 2 (app) + Task 9 (task) + Task 10 (worker/beat services)
- §8 Docker → Task 2 (db/redis) + Task 10 (full stack)
- §9 tests → each code task ships pytest; Task 10 runs the full gate
- §10 migration/transition → Task 2 (moves, deleted migrations) + Tasks 3–4 (fresh migrations)
- §11 Definition of Done → Task 10 verification

**Placeholder scan** — no TBD/TODO/"add error handling"; the one unverified external detail (remote mp3 URL) is isolated to a single constant with a working gTTS fallback and is called out explicitly.

**Type/name consistency** — `parse_pronunciation` (Task 4) returns `(ipa, pos)` and is consumed identically in Task 6; `get_tts_provider()`/`TTSProvider.synthesize` (Task 5) are consumed in Task 7; `ping` (Task 9) name matches its test; admin reverse name `admin:catalog_word_changelist` matches the `catalog` app label set in Task 2.

**Ordering note** — Postgres (`docker compose up -d db redis`) must be running from Task 2 onward for tests and `migrate`.
```
