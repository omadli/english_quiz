# Faza 1 — Bot yadrosi (Bot Core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the aiogram 3.x bot core: register Telegram users into Django, and run a skippable onboarding wizard (daily goal, study weekdays, morning/exam times, audio) that persists to a `LearningProfile`, editable via `/settings`.

**Architecture:** The `bot/` package is a separate process that calls `django.setup()` and uses the Django ORM. DB work lives in **sync** service functions; async aiogram handlers/middleware bridge to them with `asgiref.sync.sync_to_async`. FSM state is stored in Redis (DB 2). Handlers are thin glue over the service + helper layer; text is in `bot/strings.py`, keyboards in `bot/keyboards/`, so the testable logic (services, validators, keyboard builders, wizard→profile mapping) is unit-tested and handlers get light mock-based smoke tests.

**Tech Stack:** aiogram 3.x · Django 6 ORM (sync services + `sync_to_async`) · Redis FSM (`RedisStorage`) · long polling · pytest + pytest-django + pytest-asyncio.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-03-phase-1-bot-core-design.md`. Phase 0 is complete on `main`.
- Run everything via uv (pip-installed, not on PATH): `python -m uv run ...` (e.g. `python -m uv run pytest`, `python -m uv run python manage.py ...`).
- Postgres + Redis run via `docker compose up -d db redis` (needed for DB tests).
- **DB access pattern:** service functions in `bot/services/` are **sync** (plain Django ORM); handlers/middleware call them via `await sync_to_async(fn)(...)`. Do NOT use native async ORM (`aget`/`acreate`) — it complicates test transactions.
- **Testing split:** services + `apply_wizard_data` + model tests use `@pytest.mark.django_db` (sync). Validators + keyboard builders are pure sync tests. Handler/middleware smoke tests are async (pytest-asyncio, `asyncio_mode="auto"`), **mock the service layer** and aiogram objects (`unittest.mock.AsyncMock`), and use a real `FSMContext` backed by `MemoryStorage` to assert state/data. Handler tests must NOT hit the real DB.
- New app: `apps.learning` (label `learning`), added to `INSTALLED_APPS`. Model `LearningProfile` per the spec.
- Uzbek UI text lives only in `bot/strings.py`. Handlers reference constants, never inline literals.
- Weekdays: `0=Monday … 6=Sunday`, stored as `list[int]` in `LearningProfile.study_weekdays`.
- Long polling only (no webhook). FSM Redis URL = `REDIS_URL` with its DB index replaced by `2`.
- TDD; pristine test output. Commit footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Out of scope (do NOT build): daily word delivery, exams, Celery schedules (Phase 2); nudges, parent/teacher, PDF (Phase 4); group quiz (Phase 3); web (Phase 5).

### Prerequisite (once, before Task 1)

```bash
git checkout main && git pull --ff-only 2>/dev/null; git checkout -b phase-1-bot-core
```

---

### Task 1: `apps/learning` — LearningProfile model, admin, deps

**Files:**
- Create: `apps/learning/__init__.py`, `apps/learning/apps.py`, `apps/learning/models.py`, `apps/learning/admin.py`, `apps/learning/migrations/__init__.py`
- Create: `apps/learning/tests/__init__.py`, `apps/learning/tests/test_models.py`
- Modify: `config/settings/base.py` (add `apps.learning` to INSTALLED_APPS)
- Modify: `pyproject.toml` (add `pytest-asyncio` dev dep + `asyncio_mode`)
- Create (generated): `apps/learning/migrations/0001_initial.py`

**Interfaces:**
- Produces: `apps.learning.models.LearningProfile` (fields per spec §3), `apps.learning.models.default_weekdays() -> list[int]`, `LearningProfile.studies_today(weekday: int) -> bool`.

- [ ] **Step 1: Add pytest-asyncio and configure asyncio mode**

In `pyproject.toml`, add to the `[dependency-groups] dev` list:
```toml
    "pytest-asyncio>=0.24",
```
And add to `[tool.pytest.ini_options]`:
```toml
asyncio_mode = "auto"
```
Then: `python -m uv sync`

- [ ] **Step 2: Scaffold the app**

`apps/learning/__init__.py`: (empty)

`apps/learning/apps.py`:
```python
from django.apps import AppConfig


class LearningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.learning"
    label = "learning"
    verbose_name = "Learning"
```

`apps/learning/migrations/__init__.py`: (empty)

Add `"apps.learning",` to `INSTALLED_APPS` in `config/settings/base.py`, right after `"apps.catalog",`.

- [ ] **Step 3: Write the failing tests**

`apps/learning/tests/__init__.py`: (empty)

`apps/learning/tests/test_models.py`:
```python
import datetime

import pytest

from apps.accounts.models import User
from apps.learning.models import LearningProfile, default_weekdays

pytestmark = pytest.mark.django_db


def _user():
    return User.objects.create(first_name="Test")


def test_profile_defaults():
    p = LearningProfile.objects.create(user=_user())
    assert p.words_per_session == 10
    assert p.study_weekdays == [0, 1, 2, 3, 4, 5, 6]
    assert p.morning_time == datetime.time(7, 0)
    assert p.exam_time == datetime.time(20, 0)
    assert p.audio_enabled is True
    assert p.audio_repeat == 2
    assert p.timezone == "Asia/Tashkent"
    assert p.onboarded is False
    assert p.is_active is True
    assert p.current_word_order == 0


def test_studies_today():
    p = LearningProfile.objects.create(user=_user(), study_weekdays=[0, 2, 4])
    assert p.studies_today(0) is True
    assert p.studies_today(1) is False


def test_default_weekdays_is_a_fresh_list():
    first = default_weekdays()
    first.append(99)
    assert default_weekdays() == [0, 1, 2, 3, 4, 5, 6]
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m uv run pytest apps/learning/tests/test_models.py -v`
Expected: FAIL — `apps.learning.models` has no `LearningProfile`.

- [ ] **Step 5: Implement the model**

`apps/learning/models.py`:
```python
import datetime

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel


def default_weekdays() -> list[int]:
    """Mon..Sun as 0..6 — all days by default (fresh list each call)."""
    return [0, 1, 2, 3, 4, 5, 6]


class LearningProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learning_profile"
    )
    words_per_session = models.PositiveSmallIntegerField(default=10)
    study_weekdays = models.JSONField(default=default_weekdays)
    morning_time = models.TimeField(default=datetime.time(7, 0))
    exam_time = models.TimeField(default=datetime.time(20, 0))
    audio_enabled = models.BooleanField(default=True)
    audio_repeat = models.PositiveSmallIntegerField(default=2)
    timezone = models.CharField(max_length=40, default="Asia/Tashkent")
    language = models.CharField(max_length=8, default="uz")
    onboarded = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    current_book = models.ForeignKey(
        "catalog.Book", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    current_unit = models.ForeignKey(
        "catalog.Unit", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    current_word_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("Learning profile")
        verbose_name_plural = _("Learning profiles")

    def studies_today(self, weekday: int) -> bool:
        return weekday in self.study_weekdays

    def __str__(self) -> str:
        return f"LearningProfile(user={self.user_id})"
```

- [ ] **Step 6: Make migrations and run tests**

Run:
```bash
python -m uv run python manage.py makemigrations learning
python -m uv run pytest apps/learning/tests/test_models.py -v
```
Expected: migration `0001_initial` created; 3 tests PASS.

- [ ] **Step 7: Add the admin**

`apps/learning/admin.py`:
```python
from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import LearningProfile


@admin.register(LearningProfile)
class LearningProfileAdmin(ModelAdmin):
    list_display = ("user", "words_per_session", "onboarded", "is_active", "current_book")
    list_filter = ("onboarded", "is_active", "audio_enabled")
    raw_id_fields = ("user", "current_book", "current_unit")
    search_fields = ("user__first_name", "user__last_name")
```

- [ ] **Step 8: Apply migration, run full suite, commit**

Run:
```bash
python -m uv run python manage.py migrate
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning config/settings/base.py pyproject.toml uv.lock
git commit -m "feat(learning): LearningProfile model + admin, add pytest-asyncio"
```
Expected: migrate clean; full suite passes (25 total: 22 prior + 3 new); ruff clean.

---

### Task 2: Bot config + strings (+ REDIS_URL setting)

**Files:**
- Create: `bot/config.py`, `bot/strings.py`
- Modify: `config/settings/base.py` (add explicit `REDIS_URL` setting)
- Create: `bot/tests/__init__.py`, `bot/tests/test_config.py`

**Interfaces:**
- Consumes: `settings.BOT_TOKEN`, `settings.REDIS_URL`.
- Produces: `bot.config.get_bot_token() -> str` (raises `RuntimeError` if empty), `bot.config.get_fsm_redis_url() -> str` (REDIS_URL with DB index → `2`), and `bot.strings` module with the Uzbek text constants used by later tasks.

- [ ] **Step 1: Add an explicit `REDIS_URL` setting**

In `config/settings/base.py`, near the Celery block, add:
```python
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/1")
```
(The bot derives its FSM DB from this.)

- [ ] **Step 2: Write the failing tests**

`bot/tests/__init__.py`: (empty)

`bot/tests/test_config.py`:
```python
import pytest

from bot.config import get_bot_token, get_fsm_redis_url


def test_get_fsm_redis_url_replaces_db_index(settings):
    settings.REDIS_URL = "redis://redis:6379/1"
    assert get_fsm_redis_url() == "redis://redis:6379/2"


def test_get_fsm_redis_url_appends_when_no_index(settings):
    settings.REDIS_URL = "redis://redis:6379"
    assert get_fsm_redis_url() == "redis://redis:6379/2"


def test_get_bot_token_raises_when_empty(settings):
    settings.BOT_TOKEN = ""
    with pytest.raises(RuntimeError):
        get_bot_token()


def test_get_bot_token_returns_value(settings):
    settings.BOT_TOKEN = "123:abc"
    assert get_bot_token() == "123:abc"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m uv run pytest bot/tests/test_config.py -v`
Expected: FAIL — `bot.config` doesn't exist.

- [ ] **Step 4: Implement `bot/config.py`**

```python
import re

from django.conf import settings


def get_bot_token() -> str:
    token = settings.BOT_TOKEN
    if not token:
        raise RuntimeError("BOT_TOKEN is not set — put it in .env")
    return token


def get_fsm_redis_url() -> str:
    """Return REDIS_URL with its DB index forced to 2 (dedicated FSM DB)."""
    url = settings.REDIS_URL
    if re.search(r"/\d+$", url):
        return re.sub(r"/\d+$", "/2", url)
    return url.rstrip("/") + "/2"
```

- [ ] **Step 5: Implement `bot/strings.py`**

```python
# Uzbek UI text. Handlers reference these constants; no inline literals elsewhere.

WELCOME_NEW = (
    "Assalomu alaykum! 👋\n\n"
    "Men <b>4000 Essential Words</b> so'zlarini yodlashda shaxsiy mentoringizman.\n"
    "Har kuni belgilangan vaqtda yangi so'zlarni yuboraman va imtihon qilaman.\n\n"
    "Keling, avval o'quv rejangizni sozlaymiz."
)
WELCOME_BACK = "Xush kelibsiz! 👋 Sozlamalarni ko'rish uchun /settings buyrug'ini yuboring."
ONBOARD_START_BTN = "🚀 Sozlashni boshlash"
ONBOARD_DEFAULTS_BTN = "⚡ Standart bilan boshlash"

ASK_WORDS = "Kuniga (har seansda) nechta yangi so'z o'rganmoqchisiz?"
ASK_WEEKDAYS = "Qaysi kunlari o'rganasiz? Kunlarni belgilang, so'ng «Tayyor» bosing."
ASK_MORNING = "So'zlarni har kuni soat nechada yuboray? (yoki «Boshqa» bosib HH:MM yozing)"
ASK_EXAM = "Kechki imtihon vaqti nechada bo'lsin? (yoki «Boshqa» bosib HH:MM yozing)"
ASK_AUDIO = "So'zlar audio talaffuzi bilan yuborilsinmi?"
ASK_AUDIO_REPEAT = "Talaffuz necha marta takrorlansin?"
INVALID_TIME = "❌ Vaqt formati noto'g'ri. Iltimos HH:MM ko'rinishida yozing (masalan 07:30)."

WEEKDAY_NAMES = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
WEEKDAY_SHORT = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]

BTN_EVERYDAY = "Har kuni"
BTN_DONE = "✅ Tayyor"
BTN_OTHER = "Boshqa…"
BTN_AUDIO_ON = "🔊 Ha"
BTN_AUDIO_OFF = "🔇 Yo'q"
BTN_SAVE = "💾 Saqlash"

ONBOARD_DONE = "🎉 Ajoyib! Rejangiz saqlandi. Har kuni belgilangan vaqtda so'zlar yuboriladi.\nSozlamalarni /settings orqali o'zgartirishingiz mumkin."

SETTINGS_TITLE = "⚙️ <b>Sizning sozlamalaringiz</b>"
SETTINGS_WORDS = "So'z / seans"
SETTINGS_DAYS = "O'quv kunlari"
SETTINGS_MORNING = "So'z vaqti"
SETTINGS_EXAM = "Imtihon vaqti"
SETTINGS_AUDIO = "Audio"
SETTINGS_EDIT_HINT = "O'zgartirish uchun tegishli tugmani bosing."

HELP_TEXT = (
    "Buyruqlar:\n"
    "/start — boshlash / qayta ishga tushirish\n"
    "/settings — o'quv sozlamalarini ko'rish va o'zgartirish\n"
    "/cancel — joriy amalni bekor qilish\n"
    "/help — yordam"
)
CANCELLED = "Bekor qilindi."
NOTHING_TO_CANCEL = "Bekor qiladigan amal yo'q."
GENERIC_ERROR = "⚠️ Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring."
```

- [ ] **Step 6: Run tests and commit**

Run:
```bash
python -m uv run pytest bot/tests/test_config.py -v
python -m uv run ruff check bot/
git add bot/config.py bot/strings.py bot/tests config/settings/base.py
git commit -m "feat(bot): config helpers (token, FSM redis url) + Uzbek strings"
```
Expected: 4 tests PASS; ruff clean.

---

### Task 3: User service (sync ORM) + UserMiddleware

**Files:**
- Create: `bot/services/__init__.py`, `bot/services/users.py`
- Create: `bot/middlewares/__init__.py`, `bot/middlewares/user.py`
- Create: `bot/tests/test_services_users.py`, `bot/tests/test_middleware.py`

**Interfaces:**
- Consumes: `apps.accounts.models.User`, `apps.accounts.models.TelegramAccount`, `apps.learning.models.LearningProfile`, `apps.catalog.models.Book`/`Unit`.
- Produces:
  - `bot.services.users.get_or_create_user(telegram_id, username, first_name, last_name, language_code) -> tuple[User, LearningProfile, bool]`
  - `bot.services.users.update_profile(profile, **fields) -> LearningProfile`
  - `bot.services.users.set_starting_position(profile) -> LearningProfile`
  - `bot.services.users.apply_wizard_data(profile, data: dict) -> LearningProfile`
  - `bot.middlewares.user.UserMiddleware` (aiogram middleware injecting `data["user"]`, `data["profile"]`)

- [ ] **Step 1: Write the failing service tests**

`bot/tests/test_services_users.py`:
```python
import pytest

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit
from apps.learning.models import LearningProfile
from bot.services.users import (
    apply_wizard_data,
    get_or_create_user,
    set_starting_position,
    update_profile,
)

pytestmark = pytest.mark.django_db


def test_get_or_create_user_creates_everything():
    user, profile, created = get_or_create_user(
        telegram_id=555, username="ali", first_name="Ali", last_name="", language_code="uz"
    )
    assert created is True
    assert TelegramAccount.objects.get(telegram_id=555).user_id == user.id
    assert LearningProfile.objects.get(user=user).id == profile.id


def test_get_or_create_user_is_idempotent_and_updates_tg_fields():
    get_or_create_user(telegram_id=555, username="ali", first_name="Ali", last_name="", language_code="uz")
    user, profile, created = get_or_create_user(
        telegram_id=555, username="ali2", first_name="Ali", last_name="V", language_code="en"
    )
    assert created is False
    assert User.objects.count() == 1
    assert TelegramAccount.objects.get(telegram_id=555).username == "ali2"


def test_set_starting_position_picks_first_book_and_unit():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    unit = Unit.objects.create(book=book, number=1)
    _, profile, _ = get_or_create_user(telegram_id=1, username="", first_name="A", last_name="", language_code="")
    set_starting_position(profile)
    profile.refresh_from_db()
    assert profile.current_book_id == book.id
    assert profile.current_unit_id == unit.id
    assert profile.current_word_order == 0


def test_apply_wizard_data_sets_fields_and_onboards():
    Book.objects.create(number=1, title="Book 1", slug="book-1")
    _, profile, _ = get_or_create_user(telegram_id=2, username="", first_name="A", last_name="", language_code="")
    import datetime
    apply_wizard_data(profile, {
        "words_per_session": 15,
        "study_weekdays": [0, 2, 4],
        "morning_time": datetime.time(6, 30),
        "exam_time": datetime.time(21, 0),
        "audio_enabled": True,
        "audio_repeat": 3,
    })
    profile.refresh_from_db()
    assert profile.words_per_session == 15
    assert profile.study_weekdays == [0, 2, 4]
    assert profile.morning_time == datetime.time(6, 30)
    assert profile.audio_repeat == 3
    assert profile.onboarded is True
    assert profile.current_book is not None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_services_users.py -v`
Expected: FAIL — `bot.services.users` doesn't exist.

- [ ] **Step 3: Implement `bot/services/users.py`**

`bot/services/__init__.py`: (empty)

`bot/services/users.py`:
```python
from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book
from apps.learning.models import LearningProfile


def get_or_create_user(
    telegram_id: int,
    username: str,
    first_name: str,
    last_name: str,
    language_code: str,
) -> tuple[User, LearningProfile, bool]:
    """Find or create the User + TelegramAccount + LearningProfile for a Telegram user."""
    try:
        account = TelegramAccount.objects.select_related("user").get(telegram_id=telegram_id)
        account.username = username
        account.first_name = first_name
        account.last_name = last_name
        account.language_code = language_code
        account.save(update_fields=["username", "first_name", "last_name", "language_code", "updated_at"])
        user = account.user
        profile, _ = LearningProfile.objects.get_or_create(user=user)
        return user, profile, False
    except TelegramAccount.DoesNotExist:
        user = User.objects.create(first_name=first_name or "Foydalanuvchi", last_name=last_name or "")
        TelegramAccount.objects.create(
            user=user,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )
        profile = LearningProfile.objects.create(user=user)
        return user, profile, True


def update_profile(profile: LearningProfile, **fields) -> LearningProfile:
    for key, value in fields.items():
        setattr(profile, key, value)
    profile.save(update_fields=[*fields.keys(), "updated_at"])
    return profile


def set_starting_position(profile: LearningProfile) -> LearningProfile:
    book = Book.objects.filter(is_active=True).order_by("number").first()
    if book is None:
        return profile
    unit = book.units.order_by("number").first()
    profile.current_book = book
    profile.current_unit = unit
    profile.current_word_order = 0
    profile.save(update_fields=["current_book", "current_unit", "current_word_order", "updated_at"])
    return profile


def apply_wizard_data(profile: LearningProfile, data: dict) -> LearningProfile:
    """Persist collected wizard settings, mark onboarded, and set the starting position."""
    for key in (
        "words_per_session",
        "study_weekdays",
        "morning_time",
        "exam_time",
        "audio_enabled",
        "audio_repeat",
    ):
        if key in data:
            setattr(profile, key, data[key])
    profile.onboarded = True
    profile.save()
    set_starting_position(profile)
    return profile
```

- [ ] **Step 4: Run service tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_services_users.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Write the failing middleware test**

`bot/tests/test_middleware.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.middlewares.user import UserMiddleware

pytestmark = pytest.mark.asyncio


@patch("bot.middlewares.user.get_or_create_user")
async def test_middleware_injects_user_and_profile(mock_get):
    user_obj, profile_obj = MagicMock(name="user"), MagicMock(name="profile")
    mock_get.return_value = (user_obj, profile_obj, True)

    tg_user = MagicMock(id=42, username="ali", first_name="Ali", last_name=None, language_code="uz")
    handler = AsyncMock(return_value="ok")
    event = MagicMock()
    data = {"event_from_user": tg_user}

    result = await UserMiddleware()(handler, event, data)

    assert result == "ok"
    assert data["user"] is user_obj
    assert data["profile"] is profile_obj
    handler.assert_awaited_once_with(event, data)
    mock_get.assert_called_once_with(
        telegram_id=42, username="ali", first_name="Ali", last_name="", language_code="uz"
    )


@patch("bot.middlewares.user.get_or_create_user")
async def test_middleware_skips_when_no_user(mock_get):
    handler = AsyncMock(return_value="ok")
    data = {}
    result = await UserMiddleware()(handler, MagicMock(), data)
    assert result == "ok"
    assert "user" not in data
    mock_get.assert_not_called()
```

- [ ] **Step 6: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_middleware.py -v`
Expected: FAIL — `bot.middlewares.user` doesn't exist.

- [ ] **Step 7: Implement `bot/middlewares/user.py`**

`bot/middlewares/__init__.py`: (empty)

`bot/middlewares/user.py`:
```python
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from asgiref.sync import sync_to_async

from bot.services.users import get_or_create_user


class UserMiddleware(BaseMiddleware):
    """Inject the Django User + LearningProfile for the acting Telegram user."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is not None:
            user, profile, _ = await sync_to_async(get_or_create_user)(
                telegram_id=tg_user.id,
                username=tg_user.username or "",
                first_name=tg_user.first_name or "",
                last_name=tg_user.last_name or "",
                language_code=tg_user.language_code or "",
            )
            data["user"] = user
            data["profile"] = profile
        return await handler(event, data)
```

- [ ] **Step 8: Run middleware tests, full suite, commit**

Run:
```bash
python -m uv run pytest bot/tests/test_services_users.py bot/tests/test_middleware.py -v
python -m uv run pytest
python -m uv run ruff check bot/
git add bot/services bot/middlewares bot/tests/test_services_users.py bot/tests/test_middleware.py
git commit -m "feat(bot): user provisioning service + UserMiddleware"
```
Expected: all pass; ruff clean.

---

### Task 4: Validators + keyboards

**Files:**
- Create: `bot/validators.py`
- Create: `bot/keyboards/__init__.py`, `bot/keyboards/onboarding.py`, `bot/keyboards/common.py`
- Create: `bot/tests/test_validators.py`, `bot/tests/test_keyboards.py`

**Interfaces:**
- Produces:
  - `bot.validators.parse_time(text: str) -> datetime.time | None`
  - `bot.validators.toggle_weekday(days: list[int], day: int) -> list[int]` (returns a new sorted list)
  - `bot.keyboards.onboarding.words_keyboard()`, `weekdays_keyboard(selected: list[int])`, `time_keyboard(prefix: str, presets: list[str])`, `audio_keyboard()`, `audio_repeat_keyboard()`, `confirm_keyboard()`, `intro_keyboard()` → `InlineKeyboardMarkup`
  - `bot.keyboards.common.WEEKDAY_PRESETS`, callback-data prefixes (documented below)

**Callback-data scheme (used by Tasks 5–7):**
`onb:start`, `onb:defaults`, `onb:words:<N>`, `onb:wd:<0-6>`, `onb:wd:all`, `onb:wd:done`, `onb:mt:<HH:MM>`, `onb:mt:other`, `onb:et:<HH:MM>`, `onb:et:other`, `onb:audio:on`, `onb:audio:off`, `onb:rep:<1-3>`, `onb:save`. Settings edit (Task 7): `set:words`, `set:days`, `set:morning`, `set:exam`, `set:audio`.

- [ ] **Step 1: Write the failing validator tests**

`bot/tests/test_validators.py`:
```python
import datetime

import pytest

from bot.validators import parse_time, toggle_weekday


@pytest.mark.parametrize(
    "text,expected",
    [
        ("07:30", datetime.time(7, 30)),
        ("7:5", datetime.time(7, 5)),
        ("23:59", datetime.time(23, 59)),
        ("00:00", datetime.time(0, 0)),
        ("24:00", None),
        ("07:60", None),
        ("abc", None),
        ("", None),
        ("7", None),
    ],
)
def test_parse_time(text, expected):
    assert parse_time(text) == expected


def test_toggle_weekday_adds_and_removes():
    assert toggle_weekday([0, 2], 1) == [0, 1, 2]
    assert toggle_weekday([0, 1, 2], 1) == [0, 2]
    assert toggle_weekday([], 5) == [5]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_validators.py -v`
Expected: FAIL — `bot.validators` missing.

- [ ] **Step 3: Implement `bot/validators.py`**

```python
import datetime


def parse_time(text: str) -> datetime.time | None:
    """Parse 'HH:MM' (24h). Return None if malformed or out of range."""
    parts = text.strip().split(":")
    if len(parts) != 2:
        return None
    hh, mm = parts
    if not (hh.isdigit() and mm.isdigit()):
        return None
    hour, minute = int(hh), int(mm)
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return datetime.time(hour, minute)
    return None


def toggle_weekday(days: list[int], day: int) -> list[int]:
    """Add day if absent, remove if present. Returns a new sorted list."""
    result = set(days)
    if day in result:
        result.discard(day)
    else:
        result.add(day)
    return sorted(result)
```

- [ ] **Step 4: Run validator tests**

Run: `python -m uv run pytest bot/tests/test_validators.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing keyboard tests**

`bot/tests/test_keyboards.py`:
```python
from bot.keyboards.onboarding import (
    intro_keyboard,
    weekdays_keyboard,
    words_keyboard,
)


def _all_buttons(markup):
    return [btn for row in markup.inline_keyboard for btn in row]


def test_intro_keyboard_has_start_and_defaults():
    cbs = {b.callback_data for b in _all_buttons(intro_keyboard())}
    assert "onb:start" in cbs
    assert "onb:defaults" in cbs


def test_words_keyboard_offers_presets():
    cbs = {b.callback_data for b in _all_buttons(words_keyboard())}
    assert "onb:words:10" in cbs
    assert "onb:words:20" in cbs


def test_weekdays_keyboard_marks_selected():
    markup = weekdays_keyboard([0, 2])
    texts = [b.text for b in _all_buttons(markup)]
    # selected days are prefixed with a check
    assert any(t.startswith("✅") and "Du" in t for t in texts)
    assert any("Se" in t and not t.startswith("✅") for t in texts)
    cbs = {b.callback_data for b in _all_buttons(markup)}
    assert "onb:wd:done" in cbs
    assert "onb:wd:all" in cbs
```

- [ ] **Step 6: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_keyboards.py -v`
Expected: FAIL — `bot.keyboards.onboarding` missing.

- [ ] **Step 7: Implement the keyboards**

`bot/keyboards/__init__.py`: (empty)

`bot/keyboards/common.py`:
```python
MORNING_PRESETS = ["06:00", "07:00", "08:00"]
EXAM_PRESETS = ["19:00", "20:00", "21:00"]
WORDS_PRESETS = [5, 10, 15, 20, 25, 30]
```

`bot/keyboards/onboarding.py`:
```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import strings
from bot.keyboards.common import EXAM_PRESETS, MORNING_PRESETS, WORDS_PRESETS


def intro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=strings.ONBOARD_START_BTN, callback_data="onb:start")],
        [InlineKeyboardButton(text=strings.ONBOARD_DEFAULTS_BTN, callback_data="onb:defaults")],
    ])


def words_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=str(n), callback_data=f"onb:words:{n}") for n in WORDS_PRESETS]
    rows = [row[i:i + 3] for i in range(0, len(row), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def weekdays_keyboard(selected: list[int]) -> InlineKeyboardMarkup:
    day_buttons = []
    for i, name in enumerate(strings.WEEKDAY_SHORT):
        label = f"✅ {name}" if i in selected else name
        day_buttons.append(InlineKeyboardButton(text=label, callback_data=f"onb:wd:{i}"))
    rows = [day_buttons[i:i + 4] for i in range(0, len(day_buttons), 4)]
    rows.append([
        InlineKeyboardButton(text=strings.BTN_EVERYDAY, callback_data="onb:wd:all"),
        InlineKeyboardButton(text=strings.BTN_DONE, callback_data="onb:wd:done"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def time_keyboard(prefix: str, presets: list[str]) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=t, callback_data=f"{prefix}:{t}") for t in presets]
    return InlineKeyboardMarkup(inline_keyboard=[
        row,
        [InlineKeyboardButton(text=strings.BTN_OTHER, callback_data=f"{prefix}:other")],
    ])


def morning_keyboard() -> InlineKeyboardMarkup:
    return time_keyboard("onb:mt", MORNING_PRESETS)


def exam_keyboard() -> InlineKeyboardMarkup:
    return time_keyboard("onb:et", EXAM_PRESETS)


def audio_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=strings.BTN_AUDIO_ON, callback_data="onb:audio:on"),
        InlineKeyboardButton(text=strings.BTN_AUDIO_OFF, callback_data="onb:audio:off"),
    ]])


def audio_repeat_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=str(n), callback_data=f"onb:rep:{n}") for n in (1, 2, 3)
    ]])


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=strings.BTN_SAVE, callback_data="onb:save")
    ]])
```

- [ ] **Step 8: Run tests, commit**

Run:
```bash
python -m uv run pytest bot/tests/test_validators.py bot/tests/test_keyboards.py -v
python -m uv run ruff check bot/
git add bot/validators.py bot/keyboards bot/tests/test_validators.py bot/tests/test_keyboards.py
git commit -m "feat(bot): time/weekday validators + onboarding keyboards"
```
Expected: all pass; ruff clean.

---

### Task 5: Onboarding states + start handler + defaults path

**Files:**
- Create: `bot/states/__init__.py`, `bot/states/onboarding.py`
- Create: `bot/handlers/__init__.py`, `bot/handlers/start.py`
- Create: `bot/tests/test_handlers_start.py`

**Interfaces:**
- Consumes: `bot.services.users` (`apply_wizard_data`, `update_profile`), `bot.keyboards.onboarding`, `bot.strings`.
- Produces:
  - `bot.states.onboarding.OnboardingStates` (states: `words`, `weekdays`, `morning`, `exam`, `audio`, `audio_repeat`, `confirm`)
  - `bot.handlers.start.router` (aiogram `Router`) handling `/start`, `onb:start`, `onb:defaults`
  - `bot.handlers.start.DEFAULTS` dict of default wizard values

- [ ] **Step 1: Write the failing tests**

`bot/tests/test_handlers_start.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import start as start_handler
from bot.states.onboarding import OnboardingStates

pytestmark = pytest.mark.asyncio


def _state():
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=0, chat_id=1, user_id=1))


async def test_start_new_user_shows_intro_and_no_state():
    profile = MagicMock(onboarded=False)
    message = AsyncMock()
    state = _state()
    await start_handler.cmd_start(message, state, profile=profile)
    message.answer.assert_awaited()
    assert await state.get_state() is None  # waits for the user to tap a button


async def test_start_returning_user_gets_welcome_back():
    profile = MagicMock(onboarded=True)
    message = AsyncMock()
    await start_handler.cmd_start(message, _state(), profile=profile)
    args, kwargs = message.answer.call_args
    assert "settings" in (args[0] if args else kwargs.get("text", "")).lower()


async def test_begin_wizard_sets_first_state():
    callback = AsyncMock()
    state = _state()
    await start_handler.begin_wizard(callback, state)
    assert await state.get_state() == OnboardingStates.words.state
    callback.answer.assert_awaited()


@patch("bot.handlers.start.set_starting_position")
@patch("bot.handlers.start.update_profile")
async def test_use_defaults_onboards(mock_update, mock_setpos):
    profile = MagicMock()
    callback = AsyncMock()
    state = _state()
    await start_handler.use_defaults(callback, state, profile=profile)
    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["onboarded"] is True
    mock_setpos.assert_called_once_with(profile)
    assert await state.get_state() is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_handlers_start.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement states**

`bot/states/__init__.py`: (empty)

`bot/states/onboarding.py`:
```python
from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    words = State()
    weekdays = State()
    morning = State()
    exam = State()
    audio = State()
    audio_repeat = State()
    confirm = State()
```

- [ ] **Step 4: Implement the start handler**

`bot/handlers/__init__.py`: (empty)

`bot/handlers/start.py`:
```python
import datetime

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.learning.models import LearningProfile, default_weekdays
from bot import strings
from bot.keyboards.onboarding import intro_keyboard, words_keyboard
from bot.services.users import set_starting_position, update_profile
from bot.states.onboarding import OnboardingStates

router = Router()

DEFAULTS = {
    "words_per_session": 10,
    "study_weekdays": default_weekdays(),
    "morning_time": datetime.time(7, 0),
    "exam_time": datetime.time(20, 0),
    "audio_enabled": True,
    "audio_repeat": 2,
}


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, profile: LearningProfile) -> None:
    await state.clear()
    if profile.onboarded:
        await message.answer(strings.WELCOME_BACK)
        return
    await message.answer(strings.WELCOME_NEW, reply_markup=intro_keyboard())


@router.callback_query(F.data == "onb:start")
async def begin_wizard(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.words)
    await callback.message.edit_text(strings.ASK_WORDS, reply_markup=words_keyboard())


@router.callback_query(F.data == "onb:defaults")
async def use_defaults(callback: CallbackQuery, state: FSMContext, profile: LearningProfile) -> None:
    await callback.answer()
    await sync_to_async(update_profile)(profile, onboarded=True, **DEFAULTS)
    await sync_to_async(set_starting_position)(profile)
    await state.clear()
    await callback.message.edit_text(strings.ONBOARD_DONE)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_handlers_start.py -v`
Expected: 4 tests PASS.

- [ ] **Step 6: Full suite + commit**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check bot/
git add bot/states bot/handlers/__init__.py bot/handlers/start.py bot/tests/test_handlers_start.py
git commit -m "feat(bot): onboarding states + /start handler with defaults path"
```
Expected: all pass; ruff clean.

---

### Task 6: Onboarding wizard step handlers

**Files:**
- Create: `bot/handlers/onboarding.py`
- Create: `bot/tests/test_handlers_onboarding.py`

**Interfaces:**
- Consumes: `OnboardingStates`, keyboards, `bot.validators.parse_time`, `bot.services.users.apply_wizard_data`, `bot.strings`, `bot.keyboards.common` presets.
- Produces: `bot.handlers.onboarding.router` handling the wizard callbacks/messages for each state, plus `bot.handlers.onboarding.format_summary(data: dict) -> str`.

- [ ] **Step 1: Write the failing tests**

`bot/tests/test_handlers_onboarding.py`:
```python
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import onboarding as ob
from bot.states.onboarding import OnboardingStates

pytestmark = pytest.mark.asyncio


def _state():
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=0, chat_id=1, user_id=1))


def _cb(data):
    c = AsyncMock()
    c.data = data
    return c


async def test_pick_words_stores_and_advances_to_weekdays():
    state = _state()
    await state.set_state(OnboardingStates.words)
    await ob.pick_words(_cb("onb:words:15"), state)
    assert (await state.get_data())["words_per_session"] == 15
    assert await state.get_state() == OnboardingStates.weekdays.state


async def test_toggle_and_done_weekdays_advances_to_morning():
    state = _state()
    await state.set_state(OnboardingStates.weekdays)
    await ob.toggle_weekday_cb(_cb("onb:wd:0"), state)
    await ob.toggle_weekday_cb(_cb("onb:wd:2"), state)
    assert (await state.get_data())["study_weekdays"] == [0, 2]
    await ob.weekdays_done(_cb("onb:wd:done"), state)
    assert await state.get_state() == OnboardingStates.morning.state


async def test_everyday_selects_all():
    state = _state()
    await state.set_state(OnboardingStates.weekdays)
    await ob.weekdays_all(_cb("onb:wd:all"), state)
    assert (await state.get_data())["study_weekdays"] == [0, 1, 2, 3, 4, 5, 6]


async def test_pick_morning_preset_advances_to_exam():
    state = _state()
    await state.set_state(OnboardingStates.morning)
    await ob.pick_morning(_cb("onb:mt:06:00"), state)
    assert (await state.get_data())["morning_time"] == datetime.time(6, 0)
    assert await state.get_state() == OnboardingStates.exam.state


async def test_typed_morning_time_valid_advances():
    state = _state()
    await state.set_state(OnboardingStates.morning)
    msg = AsyncMock()
    msg.text = "06:45"
    await ob.typed_morning(msg, state)
    assert (await state.get_data())["morning_time"] == datetime.time(6, 45)
    assert await state.get_state() == OnboardingStates.exam.state


async def test_typed_morning_time_invalid_reprompts():
    state = _state()
    await state.set_state(OnboardingStates.morning)
    msg = AsyncMock()
    msg.text = "99:99"
    await ob.typed_morning(msg, state)
    assert "morning_time" not in (await state.get_data())
    assert await state.get_state() == OnboardingStates.morning.state
    msg.answer.assert_awaited()


async def test_audio_off_skips_repeat_to_confirm():
    state = _state()
    await state.set_state(OnboardingStates.audio)
    await ob.pick_audio(_cb("onb:audio:off"), state)
    data = await state.get_data()
    assert data["audio_enabled"] is False
    assert data["audio_repeat"] == 0
    assert await state.get_state() == OnboardingStates.confirm.state


async def test_audio_on_goes_to_repeat():
    state = _state()
    await state.set_state(OnboardingStates.audio)
    await ob.pick_audio(_cb("onb:audio:on"), state)
    assert await state.get_state() == OnboardingStates.audio_repeat.state


@patch("bot.handlers.onboarding.apply_wizard_data")
async def test_save_persists_and_clears(mock_apply):
    profile = MagicMock()
    state = _state()
    await state.set_state(OnboardingStates.confirm)
    await state.update_data(words_per_session=10, study_weekdays=[0], morning_time=datetime.time(7, 0),
                            exam_time=datetime.time(20, 0), audio_enabled=True, audio_repeat=2)
    await ob.save_wizard(_cb("onb:save"), state, profile=profile)
    mock_apply.assert_called_once()
    assert await state.get_state() is None


def test_format_summary_contains_values():
    text = ob.format_summary({
        "words_per_session": 12, "study_weekdays": [0, 2], "morning_time": datetime.time(7, 0),
        "exam_time": datetime.time(20, 0), "audio_enabled": True, "audio_repeat": 2,
    })
    assert "12" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_handlers_onboarding.py -v`
Expected: FAIL — `bot.handlers.onboarding` missing.

- [ ] **Step 3: Implement the wizard handlers**

`bot/handlers/onboarding.py`:
```python
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.learning.models import LearningProfile
from bot import strings
from bot.keyboards.onboarding import (
    audio_keyboard,
    audio_repeat_keyboard,
    confirm_keyboard,
    exam_keyboard,
    morning_keyboard,
    weekdays_keyboard,
)
from bot.services.users import apply_wizard_data
from bot.states.onboarding import OnboardingStates
from bot.validators import parse_time, toggle_weekday

router = Router()


def format_summary(data: dict) -> str:
    days = ", ".join(strings.WEEKDAY_SHORT[d] for d in data.get("study_weekdays", []))
    audio = strings.BTN_AUDIO_ON if data.get("audio_enabled") else strings.BTN_AUDIO_OFF
    lines = [
        strings.SETTINGS_TITLE,
        f"• {strings.SETTINGS_WORDS}: <b>{data.get('words_per_session')}</b>",
        f"• {strings.SETTINGS_DAYS}: <b>{days}</b>",
        f"• {strings.SETTINGS_MORNING}: <b>{data.get('morning_time'):%H:%M}</b>",
        f"• {strings.SETTINGS_EXAM}: <b>{data.get('exam_time'):%H:%M}</b>",
        f"• {strings.SETTINGS_AUDIO}: <b>{audio}</b>",
    ]
    return "\n".join(lines)


@router.callback_query(OnboardingStates.words, F.data.startswith("onb:words:"))
async def pick_words(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(words_per_session=int(callback.data.split(":")[-1]))
    await state.set_state(OnboardingStates.weekdays)
    data = await state.get_data()
    await callback.message.edit_text(
        strings.ASK_WEEKDAYS, reply_markup=weekdays_keyboard(data.get("study_weekdays", []))
    )


@router.callback_query(OnboardingStates.weekdays, F.data.regexp(r"^onb:wd:[0-6]$"))
async def toggle_weekday_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    day = int(callback.data.split(":")[-1])
    data = await state.get_data()
    days = toggle_weekday(data.get("study_weekdays", []), day)
    await state.update_data(study_weekdays=days)
    await callback.message.edit_reply_markup(reply_markup=weekdays_keyboard(days))


@router.callback_query(OnboardingStates.weekdays, F.data == "onb:wd:all")
async def weekdays_all(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    days = [0, 1, 2, 3, 4, 5, 6]
    await state.update_data(study_weekdays=days)
    await callback.message.edit_reply_markup(reply_markup=weekdays_keyboard(days))


@router.callback_query(OnboardingStates.weekdays, F.data == "onb:wd:done")
async def weekdays_done(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    if not data.get("study_weekdays"):
        await state.update_data(study_weekdays=[0, 1, 2, 3, 4, 5, 6])
    await state.set_state(OnboardingStates.morning)
    await callback.message.edit_text(strings.ASK_MORNING, reply_markup=morning_keyboard())


@router.callback_query(OnboardingStates.morning, F.data.startswith("onb:mt:"))
async def pick_morning(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    value = callback.data.split("onb:mt:")[-1]
    if value == "other":
        await callback.message.edit_text(strings.ASK_MORNING)
        return
    await state.update_data(morning_time=parse_time(value))
    await state.set_state(OnboardingStates.exam)
    await callback.message.edit_text(strings.ASK_EXAM, reply_markup=exam_keyboard())


@router.message(OnboardingStates.morning)
async def typed_morning(message: Message, state: FSMContext) -> None:
    value = parse_time(message.text or "")
    if value is None:
        await message.answer(strings.INVALID_TIME)
        return
    await state.update_data(morning_time=value)
    await state.set_state(OnboardingStates.exam)
    await message.answer(strings.ASK_EXAM, reply_markup=exam_keyboard())


@router.callback_query(OnboardingStates.exam, F.data.startswith("onb:et:"))
async def pick_exam(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    value = callback.data.split("onb:et:")[-1]
    if value == "other":
        await callback.message.edit_text(strings.ASK_EXAM)
        return
    await state.update_data(exam_time=parse_time(value))
    await state.set_state(OnboardingStates.audio)
    await callback.message.edit_text(strings.ASK_AUDIO, reply_markup=audio_keyboard())


@router.message(OnboardingStates.exam)
async def typed_exam(message: Message, state: FSMContext) -> None:
    value = parse_time(message.text or "")
    if value is None:
        await message.answer(strings.INVALID_TIME)
        return
    await state.update_data(exam_time=value)
    await state.set_state(OnboardingStates.audio)
    await message.answer(strings.ASK_AUDIO, reply_markup=audio_keyboard())


@router.callback_query(OnboardingStates.audio, F.data.in_({"onb:audio:on", "onb:audio:off"}))
async def pick_audio(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    enabled = callback.data.endswith(":on")
    await state.update_data(audio_enabled=enabled)
    if enabled:
        await state.set_state(OnboardingStates.audio_repeat)
        await callback.message.edit_text(strings.ASK_AUDIO_REPEAT, reply_markup=audio_repeat_keyboard())
    else:
        await state.update_data(audio_repeat=0)
        await state.set_state(OnboardingStates.confirm)
        data = await state.get_data()
        await callback.message.edit_text(format_summary(data), reply_markup=confirm_keyboard())


@router.callback_query(OnboardingStates.audio_repeat, F.data.startswith("onb:rep:"))
async def pick_audio_repeat(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(audio_repeat=int(callback.data.split(":")[-1]))
    await state.set_state(OnboardingStates.confirm)
    data = await state.get_data()
    await callback.message.edit_text(format_summary(data), reply_markup=confirm_keyboard())


@router.callback_query(OnboardingStates.confirm, F.data == "onb:save")
async def save_wizard(callback: CallbackQuery, state: FSMContext, profile: LearningProfile) -> None:
    await callback.answer()
    data = await state.get_data()
    await sync_to_async(apply_wizard_data)(profile, data)
    await state.clear()
    await callback.message.edit_text(strings.ONBOARD_DONE)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_handlers_onboarding.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Full suite + commit**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check bot/
git add bot/handlers/onboarding.py bot/tests/test_handlers_onboarding.py
git commit -m "feat(bot): onboarding wizard step handlers (words/days/times/audio/confirm)"
```
Expected: all pass; ruff clean.

---

### Task 7: `/settings` view + edit handlers

**Files:**
- Create: `bot/handlers/settings.py`
- Create: `bot/keyboards/settings.py`
- Create: `bot/tests/test_handlers_settings.py`

**Interfaces:**
- Consumes: `LearningProfile`, `bot.strings`, `bot.keyboards.onboarding` (reuse step keyboards), `OnboardingStates`, `bot.services.users.update_profile`.
- Produces: `bot.handlers.settings.router` handling `/settings` and `set:*` edit callbacks; `bot.handlers.settings.format_profile(profile) -> str`; `bot.keyboards.settings.settings_keyboard()`.

- [ ] **Step 1: Write the failing tests**

`bot/tests/test_handlers_settings.py`:
```python
import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import settings as st
from bot.states.onboarding import OnboardingStates

pytestmark = pytest.mark.asyncio


def _state():
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=0, chat_id=1, user_id=1))


def _profile():
    return MagicMock(
        words_per_session=10, study_weekdays=[0, 1, 2], morning_time=datetime.time(7, 0),
        exam_time=datetime.time(20, 0), audio_enabled=True, audio_repeat=2,
    )


def test_format_profile_shows_values():
    text = st.format_profile(_profile())
    assert "10" in text
    assert "07:00" in text


async def test_settings_command_shows_summary():
    message = AsyncMock()
    await st.cmd_settings(message, _state(), profile=_profile())
    message.answer.assert_awaited()


async def test_edit_words_enters_words_state():
    callback = AsyncMock()
    callback.data = "set:words"
    state = _state()
    await st.edit_words(callback, state)
    assert await state.get_state() == OnboardingStates.words.state
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_handlers_settings.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement the settings keyboard**

`bot/keyboards/settings.py`:
```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import strings


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✏️ {strings.SETTINGS_WORDS}", callback_data="set:words")],
        [InlineKeyboardButton(text=f"✏️ {strings.SETTINGS_DAYS}", callback_data="set:days")],
        [InlineKeyboardButton(text=f"✏️ {strings.SETTINGS_MORNING}", callback_data="set:morning")],
        [InlineKeyboardButton(text=f"✏️ {strings.SETTINGS_EXAM}", callback_data="set:exam")],
        [InlineKeyboardButton(text=f"✏️ {strings.SETTINGS_AUDIO}", callback_data="set:audio")],
    ])
```

- [ ] **Step 4: Implement the settings handler**

`bot/handlers/settings.py`:
```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from apps.learning.models import LearningProfile
from bot import strings
from bot.keyboards.onboarding import (
    audio_keyboard,
    exam_keyboard,
    morning_keyboard,
    weekdays_keyboard,
    words_keyboard,
)
from bot.keyboards.settings import settings_keyboard
from bot.states.onboarding import OnboardingStates

router = Router()


def format_profile(profile: LearningProfile) -> str:
    days = ", ".join(strings.WEEKDAY_SHORT[d] for d in profile.study_weekdays)
    audio = strings.BTN_AUDIO_ON if profile.audio_enabled else strings.BTN_AUDIO_OFF
    return "\n".join([
        strings.SETTINGS_TITLE,
        f"• {strings.SETTINGS_WORDS}: <b>{profile.words_per_session}</b>",
        f"• {strings.SETTINGS_DAYS}: <b>{days}</b>",
        f"• {strings.SETTINGS_MORNING}: <b>{profile.morning_time:%H:%M}</b>",
        f"• {strings.SETTINGS_EXAM}: <b>{profile.exam_time:%H:%M}</b>",
        f"• {strings.SETTINGS_AUDIO}: <b>{audio}</b>",
        "",
        strings.SETTINGS_EDIT_HINT,
    ])


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext, profile: LearningProfile) -> None:
    await state.clear()
    await message.answer(format_profile(profile), reply_markup=settings_keyboard())


@router.callback_query(F.data == "set:words")
async def edit_words(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.words)
    await callback.message.edit_text(strings.ASK_WORDS, reply_markup=words_keyboard())


@router.callback_query(F.data == "set:days")
async def edit_days(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.weekdays)
    await state.update_data(study_weekdays=[])
    await callback.message.edit_text(strings.ASK_WEEKDAYS, reply_markup=weekdays_keyboard([]))


@router.callback_query(F.data == "set:morning")
async def edit_morning(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.morning)
    await callback.message.edit_text(strings.ASK_MORNING, reply_markup=morning_keyboard())


@router.callback_query(F.data == "set:exam")
async def edit_exam(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.exam)
    await callback.message.edit_text(strings.ASK_EXAM, reply_markup=exam_keyboard())


@router.callback_query(F.data == "set:audio")
async def edit_audio(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.audio)
    await callback.message.edit_text(strings.ASK_AUDIO, reply_markup=audio_keyboard())
```

> Note: after an edit the flow re-enters the onboarding wizard states, walks the remaining steps, and `onb:save` re-persists via `apply_wizard_data` (which is idempotent and re-marks onboarded). Single-field precision is a Phase-2+ refinement; for Phase 1 the edit re-runs the affected tail of the wizard. This is intentional and acceptable.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_handlers_settings.py -v`
Expected: 3 tests PASS.

- [ ] **Step 6: Full suite + commit**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check bot/
git add bot/handlers/settings.py bot/keyboards/settings.py bot/tests/test_handlers_settings.py
git commit -m "feat(bot): /settings view + edit entry points"
```
Expected: all pass; ruff clean.

---

### Task 8: Common handlers + factory + `__main__` wiring + docs + e2e

**Files:**
- Create: `bot/handlers/common.py`, `bot/factory.py`
- Rewrite: `bot/__main__.py` (replace the Phase-0 stub)
- Create: `bot/tests/test_factory.py`
- Modify: `.env.example` (BOT_TOKEN note; FSM redis DB note), `Readme.md` (bot run section)

**Interfaces:**
- Consumes: all routers from Tasks 5–7, `bot.config`, `bot.middlewares.user.UserMiddleware`.
- Produces: `bot.factory.build_bot() -> Bot`, `bot.factory.build_dispatcher() -> Dispatcher` (storage + middleware + all routers), `bot.handlers.common.router` (/help, /cancel, global error handler).

- [ ] **Step 1: Write the failing common-handler + factory tests**

`bot/tests/test_handlers_common.py`:
```python
from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import common

pytestmark = pytest.mark.asyncio


def _state():
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=0, chat_id=1, user_id=1))


async def test_help_replies():
    message = AsyncMock()
    await common.cmd_help(message)
    message.answer.assert_awaited()


async def test_cancel_with_active_state_clears():
    state = _state()
    from bot.states.onboarding import OnboardingStates
    await state.set_state(OnboardingStates.words)
    message = AsyncMock()
    await common.cmd_cancel(message, state)
    assert await state.get_state() is None
    message.answer.assert_awaited()


async def test_cancel_with_no_state():
    message = AsyncMock()
    await common.cmd_cancel(message, _state())
    message.answer.assert_awaited()
```

`bot/tests/test_factory.py`:
```python
def test_build_dispatcher_includes_routers(settings):
    settings.REDIS_URL = "redis://localhost:6379/1"
    from bot.factory import build_dispatcher

    dp = build_dispatcher()
    # at least the four feature routers are attached
    assert len(dp.sub_routers) >= 4


def test_build_bot_uses_token(settings):
    settings.BOT_TOKEN = "123456:TESTTOKEN"
    from bot.factory import build_bot

    bot = build_bot()
    assert bot.token == "123456:TESTTOKEN"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_handlers_common.py bot/tests/test_factory.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement common handlers**

`bot/handlers/common.py`:
```python
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, Message

from bot import strings

logger = logging.getLogger("bot")
router = Router()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(strings.HELP_TEXT)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(strings.NOTHING_TO_CANCEL)
        return
    await state.clear()
    await message.answer(strings.CANCELLED)


@router.error()
async def on_error(event: ErrorEvent) -> None:
    logger.exception("Bot handler error", exc_info=event.exception)
    message = getattr(event.update, "message", None) or getattr(
        getattr(event.update, "callback_query", None), "message", None
    )
    if message is not None:
        await message.answer(strings.GENERIC_ERROR)
```

- [ ] **Step 4: Implement the factory**

`bot/factory.py`:
```python
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from bot.config import get_bot_token, get_fsm_redis_url
from bot.handlers import common, onboarding, settings, start
from bot.middlewares.user import UserMiddleware


def build_bot() -> Bot:
    return Bot(token=get_bot_token(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=RedisStorage.from_url(get_fsm_redis_url()))
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())
    dp.include_router(start.router)
    dp.include_router(onboarding.router)
    dp.include_router(settings.router)
    dp.include_router(common.router)
    return dp
```

- [ ] **Step 5: Rewrite `bot/__main__.py`**

```python
import asyncio
import logging
import os

import django

logging.basicConfig(level=logging.INFO)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()


async def main() -> None:
    from bot.factory import build_bot, build_dispatcher

    bot = build_bot()
    dp = build_dispatcher()
    logging.getLogger("bot").info("Bot started (long polling)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Run the new tests**

Run: `python -m uv run pytest bot/tests/test_handlers_common.py bot/tests/test_factory.py -v`
Expected: PASS. (`build_dispatcher` needs Redis reachable to construct `RedisStorage.from_url` — this does NOT connect immediately, it lazily connects; the test only checks routers are attached. If it errors on connection, ensure `docker compose up -d redis` is running.)

- [ ] **Step 7: Update `.env.example` and `Readme.md`**

In `.env.example`, ensure a clear `BOT_TOKEN` line with a note and confirm `REDIS_URL` present:
```dotenv
# Telegram bot token from @BotFather (required to run the bot process)
BOT_TOKEN=
```
(The bot uses Redis DB 2 for FSM, derived automatically from REDIS_URL.)

In `Readme.md`, add a "Bot" subsection under Local development:
```markdown
## Bot (Telegram)

Set `BOT_TOKEN` in `.env` (get one from @BotFather), then:

```bash
docker compose up -d db redis
python -m uv run python manage.py migrate
python -m uv run python -m bot          # long-polling bot
```
Send `/start` to your bot to register and run onboarding; `/settings` to edit.
Full stack (bot in Docker): `docker compose up --build bot`.
```

- [ ] **Step 8: Full suite + lint + e2e verification**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check .
```
Expected: all tests pass; ruff clean.

**E2E (bot boots):** the bot process needs a real `BOT_TOKEN`.
- If a token is available in `.env`: `docker compose up -d --build bot`, then `docker compose logs bot` — expect `Bot started (long polling)` with no traceback; stop after confirming.
- If NO token is available: verify the process imports and Django-bootstraps without error by running, from the repo root:
  `python -m uv run python -c "import os,django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev'); django.setup(); from bot.factory import build_dispatcher; print('dispatcher OK', len(build_dispatcher().sub_routers))"`
  Expect `dispatcher OK 4` (needs `docker compose up -d redis`). Report which path you took.

- [ ] **Step 9: Commit**

```bash
git add bot/handlers/common.py bot/factory.py bot/__main__.py bot/tests/test_handlers_common.py bot/tests/test_factory.py .env.example Readme.md
git commit -m "feat(bot): common handlers, dispatcher factory, __main__ wiring, docs"
```

---

## Self-Review (completed by plan author)

**Spec coverage** — every Phase 1 spec section maps to a task:
- §2 decisions (aiogram, sync-ORM+sync_to_async, RedisStorage, polling, strings) → Tasks 2–8
- §3 LearningProfile model + admin → Task 1
- §4 bot structure (config/strings/keyboards/states/handlers/services/middlewares) → Tasks 2–8
- §5 onboarding flow (start, wizard steps, defaults, settings edit) → Tasks 5–7
- §6 error handling (global error handler, time validation, token guard) → Tasks 2, 6, 8
- §7 tests (services, helpers, handler smoke tests) → every task ships tests; the split is enforced in Global Constraints
- §8 config (BOT_TOKEN, FSM redis DB2, compose) → Tasks 2, 8
- §9 DoD → Task 8 (full gate + e2e)

**Placeholder scan** — no TBD/TODO/"add validation"; the settings-edit re-runs-wizard-tail behavior and the token-dependent e2e are both stated explicitly with rationale, not left vague.

**Type/name consistency** — `get_or_create_user`/`update_profile`/`set_starting_position`/`apply_wizard_data` (Task 3) are consumed with the same signatures in Tasks 5–7; `OnboardingStates` state names (Task 5) match every handler filter in Tasks 6–7; keyboard builder names and callback-data strings (Task 4) match the handlers that reference them; `build_bot`/`build_dispatcher` (Task 8) match their tests. Handler tests mock the service layer (never hit the DB), per the Global Constraints testing split.

**Ordering note** — `docker compose up -d db redis` must be running for DB-backed tests (Tasks 1, 3) and for `build_dispatcher`/e2e (Task 8).
