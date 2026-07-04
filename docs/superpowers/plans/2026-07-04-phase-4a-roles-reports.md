# Faza 4a — Rollar, Referal & Hisobotlar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let parents/teachers connect to a learner via a Telegram deep-link referral and receive that learner's progress report — on demand (`/report`) and on a daily schedule — built from the already-persisted delivery/exam data.

**Architecture:** A new `apps/relations` app persists `ReferralToken` (one-time) and `Guardianship` (guardian↔learner). A guardian runs `/parent` or `/teacher` → gets a `t.me/<bot>?start=g<token>` link; the learner opens it, and Phase-1's `cmd_start` (extended to read the start payload) redeems the token via `sync_to_async`, creating the Guardianship. Report generation is a sync service over `DailySession`/`ExamQuestion`; `/report` serves it on demand and a Celery Beat crontab task (`dispatch_guardian_reports`) pushes it daily.

**Tech Stack:** Django 6 ORM (sync) · aiogram 3.x (deep-link start, commands) · sync_to_async · Celery + django-celery-beat crontab · pytest + pytest-django + pytest-asyncio.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-04-phase-4a-roles-reports-design.md`. Phases 0/1/2a/2b/3 complete on `main`.
- Run via uv (not on PATH): `python -m uv run pytest`, `python -m uv run python manage.py ...`.
- Postgres + Redis via `docker compose up -d db redis` for DB tests.
- New app `apps.relations` (label `relations`) in INSTALLED_APPS. Models `ReferralToken`/`Guardianship` inherit `apps.common.models.TimeStampedModel`.
- Referral direction: the GUARDIAN generates the link; the LEARNER opens `?start=g<token>` to connect. Token is one-time (`is_active=False` after redemption).
- Roles: `parent`/`teacher` (TextChoices). `Guardianship` unique on `(guardian, learner)`.
- Deep-link redemption happens in Phase-1 `bot/handlers/start.py:cmd_start` by reading `command.args` (a `g<token>` payload) — must NOT break the existing onboarding flow (extend, don't replace).
- Async handlers reach the ORM ONLY via `sync_to_async`.
- Report content from `DailySession` (words count, score/total, status) + `compute_streak` (consecutive `completed` days). Streak uses `timezone.localdate()` (TIME_ZONE = Asia/Tashkent).
- Settings: `GUARDIAN_REPORT_HOUR` (default 21), `BOT_USERNAME` (default ""; fall back to `bot.get_me().username` at runtime).
- Daily reports via a Beat CRONTAB (`hour=GUARDIAN_REPORT_HOUR, minute=0`), registered by `setup_periodic_tasks`.
- OUT of scope (Phase 4b): nudges, streak badges/gamification, periodic quiz polls, monthly top, duels; PDF download.
- TDD; pristine output. Commit footer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

### Prerequisite (once, before Task 1)

```bash
git checkout main && git checkout -b phase-4a-roles-reports
```

---

### Task 1: `apps/relations` app + models + admin + settings

**Files:**
- Create: `apps/relations/__init__.py`, `apps/relations/apps.py`, `apps/relations/models.py`, `apps/relations/admin.py`, `apps/relations/migrations/__init__.py`
- Create: `apps/relations/tests/__init__.py`, `apps/relations/tests/test_models.py`
- Modify: `config/settings/base.py` (INSTALLED_APPS + `GUARDIAN_REPORT_HOUR` + `BOT_USERNAME`)
- Create (generated): `apps/relations/migrations/0001_initial.py`

**Interfaces:**
- Produces: `apps.relations.models.ReferralToken` (token unique via `_make_token` default, issuer FK, role choices, used_by/used_at, is_active), `Guardianship` (guardian FK related_name="wards_links", learner FK related_name="guardian_links", role, status; unique (guardian, learner)). Settings `GUARDIAN_REPORT_HOUR`, `BOT_USERNAME`.

- [ ] **Step 1: Scaffold the app**

`apps/relations/__init__.py`: (empty). `apps/relations/migrations/__init__.py`: (empty).

`apps/relations/apps.py`:
```python
from django.apps import AppConfig


class RelationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.relations"
    label = "relations"
    verbose_name = "Relations"
```
Add `"apps.relations",` to `INSTALLED_APPS` in `config/settings/base.py` (after `"apps.quiz",`).

- [ ] **Step 2: Write the failing tests**

`apps/relations/tests/__init__.py`: (empty)

`apps/relations/tests/test_models.py`:
```python
import pytest
from django.db import IntegrityError

from apps.accounts.models import User
from apps.relations.models import Guardianship, ReferralToken

pytestmark = pytest.mark.django_db


def test_referral_token_auto_token_and_defaults():
    issuer = User.objects.create(first_name="P")
    t = ReferralToken.objects.create(issuer=issuer, role=ReferralToken.Role.PARENT)
    assert t.token  # auto-generated, non-empty
    assert t.is_active is True
    assert t.used_by is None
    # two tokens differ
    t2 = ReferralToken.objects.create(issuer=issuer, role=ReferralToken.Role.PARENT)
    assert t.token != t2.token


def test_guardianship_unique_per_pair():
    g = User.objects.create(first_name="G")
    l = User.objects.create(first_name="L")
    Guardianship.objects.create(guardian=g, learner=l, role=Guardianship.Role.PARENT)
    assert g.wards_links.count() == 1
    assert l.guardian_links.count() == 1
    with pytest.raises(IntegrityError):
        Guardianship.objects.create(guardian=g, learner=l, role=Guardianship.Role.TEACHER)


def test_settings_present(settings):
    assert isinstance(settings.GUARDIAN_REPORT_HOUR, int)
    assert isinstance(settings.BOT_USERNAME, str)
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m uv run pytest apps/relations/tests/test_models.py -v`
Expected: FAIL — models / settings missing.

- [ ] **Step 4: Implement `apps/relations/models.py`**

```python
import secrets

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


def _make_token() -> str:
    return secrets.token_urlsafe(16)


class ReferralToken(TimeStampedModel):
    class Role(models.TextChoices):
        PARENT = "parent", "Parent"
        TEACHER = "teacher", "Teacher"

    token = models.CharField(max_length=32, unique=True, db_index=True, default=_make_token)
    issuer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_tokens"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"ReferralToken({self.role}, active={self.is_active})"


class Guardianship(TimeStampedModel):
    class Role(models.TextChoices):
        PARENT = "parent", "Parent"
        TEACHER = "teacher", "Teacher"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    guardian = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wards_links"
    )
    learner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="guardian_links"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["guardian", "learner"], name="uniq_guardian_learner")
        ]

    def __str__(self) -> str:
        return f"Guardianship({self.guardian_id}->{self.learner_id}, {self.role})"
```

- [ ] **Step 5: Add settings**

In `config/settings/base.py`, near the other app settings, add:
```python
GUARDIAN_REPORT_HOUR = env.int("GUARDIAN_REPORT_HOUR", default=21)
BOT_USERNAME = env("BOT_USERNAME", default="")
```

- [ ] **Step 6: Make migrations and run tests**

Run:
```bash
python -m uv run python manage.py makemigrations relations
python -m uv run pytest apps/relations/tests/test_models.py -v
```
Expected: migration created; 3 tests PASS.

- [ ] **Step 7: Add admin**

`apps/relations/admin.py`:
```python
from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Guardianship, ReferralToken


@admin.register(ReferralToken)
class ReferralTokenAdmin(ModelAdmin):
    list_display = ("token", "issuer", "role", "is_active", "used_by", "used_at")
    list_filter = ("role", "is_active")
    raw_id_fields = ("issuer", "used_by")


@admin.register(Guardianship)
class GuardianshipAdmin(ModelAdmin):
    list_display = ("guardian", "learner", "role", "status")
    list_filter = ("role", "status")
    raw_id_fields = ("guardian", "learner")
```

- [ ] **Step 8: Migrate, full suite, ruff, commit**

Run:
```bash
python -m uv run python manage.py migrate
python -m uv run pytest
python -m uv run ruff check .
git add apps/relations config/settings/base.py
git commit -m "feat(relations): ReferralToken + Guardianship models + admin + settings"
```
Expected: migrate clean; full suite passes (151 prior + 3 new = 154); ruff clean.

---

### Task 2: Referral service

**Files:**
- Create: `apps/relations/services/__init__.py`, `apps/relations/services/referral.py`
- Create: `apps/relations/tests/test_referral.py`

**Interfaces:**
- Produces:
  - `apps.relations.services.referral.create_referral_token(issuer, role) -> ReferralToken`
  - `apps.relations.services.referral.redeem_token(token_str, learner) -> Guardianship | None` — None if token missing/inactive or learner is the issuer; else create (get_or_create) the Guardianship, mark the token used, return it.

- [ ] **Step 1: Write the failing tests**

`apps/relations/tests/test_referral.py`:
```python
import pytest

from apps.accounts.models import User
from apps.relations.models import Guardianship, ReferralToken
from apps.relations.services.referral import create_referral_token, redeem_token

pytestmark = pytest.mark.django_db


def test_create_token():
    issuer = User.objects.create(first_name="P")
    t = create_referral_token(issuer, ReferralToken.Role.PARENT)
    assert t.is_active is True
    assert t.issuer_id == issuer.id


def test_redeem_creates_guardianship_and_consumes_token():
    parent = User.objects.create(first_name="P")
    child = User.objects.create(first_name="C")
    t = create_referral_token(parent, ReferralToken.Role.PARENT)
    g = redeem_token(t.token, child)
    assert g is not None
    assert g.guardian_id == parent.id
    assert g.learner_id == child.id
    assert g.role == "parent"
    t.refresh_from_db()
    assert t.is_active is False
    assert t.used_by_id == child.id
    # cannot reuse
    assert redeem_token(t.token, child) is None


def test_redeem_unknown_token_returns_none():
    child = User.objects.create(first_name="C")
    assert redeem_token("nope", child) is None


def test_cannot_link_to_self():
    parent = User.objects.create(first_name="P")
    t = create_referral_token(parent, ReferralToken.Role.PARENT)
    assert redeem_token(t.token, parent) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/relations/tests/test_referral.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/relations/services/referral.py`**

`apps/relations/services/__init__.py`: (empty)

`apps/relations/services/referral.py`:
```python
from django.utils import timezone

from apps.relations.models import Guardianship, ReferralToken


def create_referral_token(issuer, role: str) -> ReferralToken:
    return ReferralToken.objects.create(issuer=issuer, role=role)


def redeem_token(token_str: str, learner) -> Guardianship | None:
    token = (
        ReferralToken.objects.select_related("issuer")
        .filter(token=token_str, is_active=True)
        .first()
    )
    if token is None or token.issuer_id == learner.id:
        return None
    guardianship, _ = Guardianship.objects.get_or_create(
        guardian=token.issuer, learner=learner, defaults={"role": token.role}
    )
    token.is_active = False
    token.used_by = learner
    token.used_at = timezone.now()
    token.save(update_fields=["is_active", "used_by", "used_at", "updated_at"])
    return guardianship
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/relations/tests/test_referral.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/relations/services apps/relations/tests/test_referral.py
git commit -m "feat(relations): create_referral_token + redeem_token"
```

---

### Task 3: Report service

**Files:**
- Create: `apps/relations/services/reports.py`
- Create: `apps/relations/tests/test_reports.py`

**Interfaces:**
- Consumes: `DailySession` (Phase 2a), `Guardianship`.
- Produces:
  - `apps.relations.services.reports.guardian_wards(guardian) -> list[User]` — the learners of the guardian's active guardianships.
  - `apps.relations.services.reports.compute_streak(learner) -> int` — consecutive `completed` DailySession days up to today (`timezone.localdate()`).
  - `apps.relations.services.reports.build_learner_report(learner, date) -> str` — HTML report for that date.

- [ ] **Step 1: Write the failing tests**

`apps/relations/tests/test_reports.py`:
```python
import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.learning.models import DailySession
from apps.relations.models import Guardianship
from apps.relations.services.reports import build_learner_report, compute_streak, guardian_wards

pytestmark = pytest.mark.django_db


def test_guardian_wards_lists_active_learners():
    g = User.objects.create(first_name="G")
    l1 = User.objects.create(first_name="L1")
    l2 = User.objects.create(first_name="L2")
    Guardianship.objects.create(guardian=g, learner=l1, role="parent")
    Guardianship.objects.create(guardian=g, learner=l2, role="parent", status=Guardianship.Status.REVOKED)
    wards = guardian_wards(g)
    assert l1 in wards
    assert l2 not in wards


def test_compute_streak_counts_consecutive_completed_days():
    u = User.objects.create(first_name="U")
    today = timezone.localdate()
    for delta in (0, 1, 2):  # today, yesterday, 2 days ago
        DailySession.objects.create(user=u, date=today - datetime.timedelta(days=delta),
                                    status=DailySession.Status.COMPLETED)
    # a gap at day 4 (day 3 missing) shouldn't extend
    DailySession.objects.create(user=u, date=today - datetime.timedelta(days=4),
                                status=DailySession.Status.COMPLETED)
    assert compute_streak(u) == 3


def test_build_report_with_and_without_data():
    u = User.objects.create(first_name="Ali")
    today = timezone.localdate()
    # no session today
    text = build_learner_report(u, today)
    assert "Ali" in text
    # with a completed session
    DailySession.objects.create(user=u, date=today, status=DailySession.Status.COMPLETED,
                                score=8, total=10)
    text2 = build_learner_report(u, today)
    assert "8/10" in text2
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/relations/tests/test_reports.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/relations/services/reports.py`**

```python
import datetime

from django.utils import timezone

from apps.learning.models import DailySession
from apps.relations.models import Guardianship


def guardian_wards(guardian) -> list:
    links = (
        Guardianship.objects.filter(guardian=guardian, status=Guardianship.Status.ACTIVE)
        .select_related("learner")
        .order_by("id")
    )
    return [link.learner for link in links]


def compute_streak(learner) -> int:
    dates = set(
        DailySession.objects.filter(
            user=learner, status=DailySession.Status.COMPLETED
        ).values_list("date", flat=True)
    )
    streak = 0
    day = timezone.localdate()
    while day in dates:
        streak += 1
        day -= datetime.timedelta(days=1)
    return streak


def build_learner_report(learner, date) -> str:
    name = learner.full_name or str(learner.pk)
    lines = [f"📊 <b>{name}</b> — {date:%d.%m.%Y}"]
    session = DailySession.objects.filter(user=learner, date=date).first()
    if session is None:
        lines.append("Bugun faoliyat yo'q.")
    else:
        lines.append(f"• So'zlar: {session.words.count()}")
        if session.total:
            lines.append(f"• Imtihon: {session.score or 0}/{session.total}")
        lines.append(f"• Holat: {session.get_status_display()}")
    lines.append(f"🔥 Streak: {compute_streak(learner)} kun")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/relations/tests/test_reports.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/relations/services/reports.py apps/relations/tests/test_reports.py
git commit -m "feat(relations): guardian_wards + compute_streak + build_learner_report"
```

---

### Task 4: Deep-link redemption in `cmd_start`

**Files:**
- Modify: `bot/handlers/start.py`, `bot/strings.py`
- Modify: `bot/tests/test_handlers_start.py`

**Interfaces:**
- Consumes: `redeem_token` (Task 2).
- Produces: `bot.handlers.start.cmd_start` now accepts `command: CommandObject` + injected `user`, redeems a `g<token>` start payload before the onboarding branch.

- [ ] **Step 1: Update the tests**

Replace `bot/tests/test_handlers_start.py`'s `cmd_start` tests to pass `command` + `user`, and add a referral test. The FULL updated relevant tests:
```python
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import start as start_handler
from bot.states.onboarding import OnboardingStates


def _state():
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=0, chat_id=1, user_id=1))


def _cmd(args=None):
    return CommandObject(command="start", args=args)


pytestmark = pytest.mark.asyncio


async def test_start_new_user_shows_intro_and_no_state():
    profile = MagicMock(onboarded=False)
    message = AsyncMock()
    state = _state()
    await start_handler.cmd_start(message, state, _cmd(), user=MagicMock(), profile=profile)
    message.answer.assert_awaited()
    assert await state.get_state() is None


async def test_start_returning_user_gets_welcome_back():
    profile = MagicMock(onboarded=True)
    message = AsyncMock()
    await start_handler.cmd_start(message, _state(), _cmd(), user=MagicMock(), profile=profile)
    args, kwargs = message.answer.call_args
    assert "settings" in (args[0] if args else kwargs.get("text", "")).lower()


@patch("bot.handlers.start.redeem_token")
async def test_start_with_referral_payload_redeems(mock_redeem):
    mock_redeem.return_value = MagicMock()  # a Guardianship
    profile = MagicMock(onboarded=True)
    user = MagicMock()
    message = AsyncMock()
    await start_handler.cmd_start(message, _state(), _cmd(args="gABC123"), user=user, profile=profile)
    mock_redeem.assert_called_once_with("ABC123", user)
    assert message.answer.await_count >= 1


@patch("bot.handlers.start.redeem_token")
async def test_start_without_payload_does_not_redeem(mock_redeem):
    profile = MagicMock(onboarded=True)
    message = AsyncMock()
    await start_handler.cmd_start(message, _state(), _cmd(), user=MagicMock(), profile=profile)
    mock_redeem.assert_not_called()
```
(Keep the existing `begin_wizard` / `use_defaults` tests unchanged — they don't touch `cmd_start`.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_handlers_start.py -v`
Expected: FAIL — `cmd_start` doesn't accept `command`/`user` or call `redeem_token`.

- [ ] **Step 3: Add strings**

In `bot/strings.py`, add:
```python
LINKED_OK = "✅ Muvaffaqiyatli ulandingiz! Endi hisobotlarni olib turasiz."
```

- [ ] **Step 4: Update `bot/handlers/start.py`**

Update the imports and `cmd_start` only (leave `begin_wizard`/`use_defaults`/`DEFAULTS` unchanged):
```python
from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.accounts.models import User
from apps.learning.models import LearningProfile, default_weekdays
from apps.relations.services.referral import redeem_token
from bot import strings
from bot.keyboards.onboarding import intro_keyboard, words_keyboard
from bot.services.users import set_starting_position, update_profile
from bot.states.onboarding import OnboardingStates


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, command: CommandObject, user: User, profile: LearningProfile
) -> None:
    await state.clear()
    payload = command.args or ""
    if payload.startswith("g"):
        guardianship = await sync_to_async(redeem_token)(payload[1:], user)
        if guardianship is not None:
            await message.answer(strings.LINKED_OK)
    if profile.onboarded:
        await message.answer(strings.WELCOME_BACK)
        return
    await message.answer(strings.WELCOME_NEW, reply_markup=intro_keyboard())
```
(The `router = Router()` line already exists above these handlers — do not duplicate it.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_handlers_start.py -v`
Expected: all PASS (including the two referral tests + the unchanged wizard tests).

- [ ] **Step 6: Full suite + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/handlers/start.py bot/strings.py bot/tests/test_handlers_start.py
git commit -m "feat(bot): redeem referral deep-link in /start"
```
Expected: all pass; ruff clean.

---

### Task 5: `/parent` + `/teacher` handlers

**Files:**
- Create: `bot/handlers/relations.py`
- Modify: `bot/strings.py`
- Create: `bot/tests/test_handlers_relations.py`

**Interfaces:**
- Consumes: `create_referral_token` (Task 2), `ReferralToken.Role`.
- Produces: `bot.handlers.relations.router` with `/parent` + `/teacher` handlers; `bot.handlers.relations.bot_username(bot) -> str`.

- [ ] **Step 1: Write the failing test**

`bot/tests/test_handlers_relations.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import relations

pytestmark = pytest.mark.asyncio


async def test_bot_username_from_settings(settings):
    settings.BOT_USERNAME = "mybot"
    assert await relations.bot_username(AsyncMock()) == "mybot"


async def test_bot_username_falls_back_to_get_me(settings):
    settings.BOT_USERNAME = ""
    bot = AsyncMock()
    me = MagicMock()
    me.username = "runtimebot"
    bot.get_me.return_value = me
    assert await relations.bot_username(bot) == "runtimebot"


@patch("bot.handlers.relations.create_referral_token")
async def test_cmd_parent_sends_deep_link(mock_create, settings):
    settings.BOT_USERNAME = "mybot"
    token = MagicMock()
    token.token = "TOK123"
    mock_create.return_value = token
    message = AsyncMock()
    message.bot = AsyncMock()
    await relations.cmd_parent(message, user=MagicMock())
    mock_create.assert_called_once()
    sent = message.answer.call_args.args[0]
    assert "t.me/mybot?start=gTOK123" in sent
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_handlers_relations.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Add strings**

In `bot/strings.py`, add:
```python
PARENT_LINK = (
    "👨‍👩‍👧 Ota-ona rejimi.\nFarzandingizga shu havolani yuboring — u bosgach ulanadi va "
    "siz kunlik hisobot olib turasiz:\n\n{link}"
)
TEACHER_LINK = (
    "👨‍🏫 Ustoz rejimi.\nO'quvchingizga shu havolani yuboring — u bosgach ulanadi va "
    "siz kunlik hisobot olib turasiz:\n\n{link}"
)
```

- [ ] **Step 4: Implement `bot/handlers/relations.py`**

```python
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.conf import settings

from apps.accounts.models import User
from apps.relations.models import ReferralToken
from apps.relations.services.referral import create_referral_token
from bot import strings

router = Router()


async def bot_username(bot: Bot) -> str:
    if settings.BOT_USERNAME:
        return settings.BOT_USERNAME
    me = await bot.get_me()
    return me.username


async def _send_link(message: Message, user: User, role: str, template: str) -> None:
    token = await sync_to_async(create_referral_token)(user, role)
    username = await bot_username(message.bot)
    link = f"https://t.me/{username}?start=g{token.token}"
    await message.answer(template.format(link=link))


@router.message(Command("parent"))
async def cmd_parent(message: Message, user: User) -> None:
    await _send_link(message, user, ReferralToken.Role.PARENT, strings.PARENT_LINK)


@router.message(Command("teacher"))
async def cmd_teacher(message: Message, user: User) -> None:
    await _send_link(message, user, ReferralToken.Role.TEACHER, strings.TEACHER_LINK)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_handlers_relations.py -v`
Expected: 3 tests PASS.

- [ ] **Step 6: Full suite + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/handlers/relations.py bot/strings.py bot/tests/test_handlers_relations.py
git commit -m "feat(bot): /parent + /teacher generate referral deep-links"
```
Expected: all pass; ruff clean.

---

### Task 6: `/report` handler

**Files:**
- Modify: `bot/handlers/relations.py`, `bot/strings.py`
- Create: `bot/keyboards/relations.py`
- Modify: `bot/tests/test_handlers_relations.py`

**Interfaces:**
- Consumes: `guardian_wards`/`build_learner_report` (Task 3).
- Produces: `bot.handlers.relations` gains `/report` + a `rep:<learner_id>` callback; `bot.keyboards.relations.wards_keyboard(wards)`.

- [ ] **Step 1: Write the failing tests**

Add to `bot/tests/test_handlers_relations.py`:
```python
@patch("bot.handlers.relations.build_learner_report", return_value="REPORT-TEXT")
@patch("bot.handlers.relations.guardian_wards")
async def test_report_single_ward_sends_report(mock_wards, mock_build):
    ward = MagicMock()
    mock_wards.return_value = [ward]
    message = AsyncMock()
    await relations.cmd_report(message, user=MagicMock())
    mock_build.assert_called_once()
    message.answer.assert_awaited_with("REPORT-TEXT")


@patch("bot.handlers.relations.guardian_wards", return_value=[])
async def test_report_no_wards(mock_wards):
    message = AsyncMock()
    await relations.cmd_report(message, user=MagicMock())
    message.answer.assert_awaited()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_handlers_relations.py -v`
Expected: FAIL — `cmd_report` missing.

- [ ] **Step 3: Add strings + keyboard**

In `bot/strings.py`, add:
```python
NO_WARDS = "Hali hech kim ulanmagan. /parent yoki /teacher bilan havola oling."
PICK_WARD = "Kimning hisobotini ko'rmoqchisiz?"
```

`bot/keyboards/relations.py`:
```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def wards_keyboard(wards) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=w.full_name or str(w.pk), callback_data=f"rep:{w.pk}")]
        for w in wards
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
```

- [ ] **Step 4: Add the handlers to `bot/handlers/relations.py`**

Add imports + handlers:
```python
from aiogram import F
from aiogram.types import CallbackQuery
from django.utils import timezone

from apps.relations.models import Guardianship
from apps.relations.services.reports import build_learner_report, guardian_wards
from bot.keyboards.relations import wards_keyboard


@router.message(Command("report"))
async def cmd_report(message: Message, user: User) -> None:
    wards = await sync_to_async(guardian_wards)(user)
    if not wards:
        await message.answer(strings.NO_WARDS)
        return
    if len(wards) == 1:
        text = await sync_to_async(build_learner_report)(wards[0], timezone.localdate())
        await message.answer(text)
        return
    await message.answer(strings.PICK_WARD, reply_markup=wards_keyboard(wards))


@router.callback_query(F.data.startswith("rep:"))
async def pick_ward_report(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    learner_id = int(callback.data.split(":")[-1])
    linked = await sync_to_async(
        Guardianship.objects.filter(
            guardian=user, learner_id=learner_id, status=Guardianship.Status.ACTIVE
        ).exists
    )()
    if not linked:
        return
    learner = await sync_to_async(_get_learner)(learner_id)
    text = await sync_to_async(build_learner_report)(learner, timezone.localdate())
    await callback.message.answer(text)


def _get_learner(learner_id: int) -> User:
    return User.objects.get(pk=learner_id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_handlers_relations.py -v`
Expected: all PASS.

- [ ] **Step 6: Full suite + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/handlers/relations.py bot/keyboards/relations.py bot/strings.py bot/tests/test_handlers_relations.py
git commit -m "feat(bot): /report — on-demand learner reports for guardians"
```
Expected: all pass; ruff clean.

---

### Task 7: Daily guardian-report Beat task + registration

**Files:**
- Create: `apps/relations/tasks.py`
- Modify: `apps/learning/management/commands/setup_periodic_tasks.py`
- Create: `apps/relations/tests/test_tasks.py`
- Modify: `apps/learning/tests/test_setup_periodic_tasks.py`

**Interfaces:**
- Consumes: `guardian_wards`/`build_learner_report` (Task 3), `send_daily` (Phase 2a sender), `Guardianship`.
- Produces: `apps.relations.tasks.dispatch_guardian_reports()` (shared_task); `setup_periodic_tasks` also registers it on a daily CRONTAB (`hour=GUARDIAN_REPORT_HOUR, minute=0`).

- [ ] **Step 1: Write the failing tests**

`apps/relations/tests/test_tasks.py`:
```python
from unittest.mock import patch

import pytest

from apps.accounts.models import TelegramAccount, User
from apps.relations.models import Guardianship
from apps.relations.tasks import dispatch_guardian_reports

pytestmark = pytest.mark.django_db


@patch("apps.relations.tasks.send_daily")
@patch("apps.relations.tasks.build_learner_report", return_value="RPT")
def test_dispatch_sends_one_report_per_active_ward(mock_build, mock_send):
    guardian = User.objects.create(first_name="G")
    TelegramAccount.objects.create(user=guardian, telegram_id=777)
    l1 = User.objects.create(first_name="L1")
    l2 = User.objects.create(first_name="L2")
    Guardianship.objects.create(guardian=guardian, learner=l1, role="parent")
    Guardianship.objects.create(guardian=guardian, learner=l2, role="parent",
                                status=Guardianship.Status.REVOKED)

    dispatch_guardian_reports()

    # one active ward (l1) → one send to the guardian's telegram
    assert mock_send.call_count == 1
    assert mock_send.call_args.args[0] == 777
```

Add to `apps/learning/tests/test_setup_periodic_tasks.py`:
```python
def test_setup_registers_guardian_report_crontab():
    from django_celery_beat.models import PeriodicTask

    call_command("setup_periodic_tasks")
    task = PeriodicTask.objects.get(name="dispatch_guardian_reports")
    assert task.task == "apps.relations.tasks.dispatch_guardian_reports"
    assert task.crontab is not None
    # idempotent
    call_command("setup_periodic_tasks")
    assert PeriodicTask.objects.filter(name="dispatch_guardian_reports").count() == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/relations/tests/test_tasks.py apps/learning/tests/test_setup_periodic_tasks.py -v`
Expected: FAIL — task + crontab registration missing.

- [ ] **Step 3: Implement `apps/relations/tasks.py`**

```python
from celery import shared_task
from django.utils import timezone

from apps.relations.models import Guardianship
from apps.relations.services.reports import build_learner_report
from bot.sender import send_daily


@shared_task
def dispatch_guardian_reports() -> None:
    date = timezone.localdate()
    links = Guardianship.objects.filter(status=Guardianship.Status.ACTIVE).select_related(
        "guardian__telegram", "learner"
    )
    for link in links.iterator():
        account = getattr(link.guardian, "telegram", None)
        if account is None or account.blocked_bot:
            continue
        text = build_learner_report(link.learner, date)
        send_daily(account.telegram_id, None, [{"caption": text, "image": None, "audio": None}])
```

- [ ] **Step 4: Extend `setup_periodic_tasks`**

In `apps/learning/management/commands/setup_periodic_tasks.py`, after the interval-task loop, register the crontab task:
```python
        from django.conf import settings
        from django_celery_beat.models import CrontabSchedule

        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour=str(settings.GUARDIAN_REPORT_HOUR),
            day_of_week="*", day_of_month="*", month_of_year="*",
        )
        PeriodicTask.objects.update_or_create(
            name="dispatch_guardian_reports",
            defaults={"crontab": crontab, "interval": None,
                      "task": "apps.relations.tasks.dispatch_guardian_reports"},
        )
```
(Keep the existing `IntervalSchedule` import and the three interval tasks intact.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest apps/relations/tests/test_tasks.py apps/learning/tests/test_setup_periodic_tasks.py -v`
Expected: all PASS.

- [ ] **Step 6: Full suite + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/relations/tasks.py apps/learning/management/commands/setup_periodic_tasks.py apps/relations/tests/test_tasks.py apps/learning/tests/test_setup_periodic_tasks.py
git commit -m "feat(relations): daily guardian-report Beat task + crontab registration"
```
Expected: all pass; ruff clean.

---

### Task 8: Wire router into factory + docs + gate

**Files:**
- Modify: `bot/factory.py`, `Readme.md`
- Create: `bot/tests/test_factory_relations.py`

**Interfaces:**
- Produces: `relations.router` included in `build_dispatcher`; Readme documents parent/teacher/report usage.

- [ ] **Step 1: Write the failing test**

`bot/tests/test_factory_relations.py`:
```python
def test_dispatcher_includes_relations_router(settings):
    settings.REDIS_URL = "redis://localhost:6379/1"
    from bot.factory import build_dispatcher

    dp = build_dispatcher()
    assert len(dp.sub_routers) >= 7  # start, onboarding, settings, common, quiz, group_quiz, relations
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_factory_relations.py -v`
Expected: FAIL — only 6 routers wired.

- [ ] **Step 3: Wire the router in `bot/factory.py`**

Add `relations` to the handlers import and include it:
```python
from bot.handlers import common, group_quiz, onboarding, quiz, relations, settings, start
```
and, in `build_dispatcher`, after `dp.include_router(group_quiz.router)`:
```python
    dp.include_router(relations.router)
```

- [ ] **Step 4: Run the test**

Run: `python -m uv run pytest bot/tests/test_factory_relations.py bot/tests/test_factory.py bot/tests/test_factory_group_quiz.py -v`
Expected: PASS (≥7, and the existing ≥4 / ≥6 checks still hold).

- [ ] **Step 5: Update `Readme.md`**

Add a "Parent / Teacher reports" subsection under the Bot section:
```markdown
## Parent / Teacher reports

A parent or teacher sends `/parent` (or `/teacher`) to the bot to get a
one-time deep-link (`t.me/<bot>?start=g...`). They forward it to their
child/student, who taps it to connect. The guardian then gets a daily
progress report (words learned, exam score, streak) at `GUARDIAN_REPORT_HOUR`,
and can request it any time with `/report`. (Run `setup_periodic_tasks` once
after migrating to register the daily job.)
```

- [ ] **Step 6: Full gate + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/factory.py Readme.md bot/tests/test_factory_relations.py
git commit -m "feat(relations): wire relations router into dispatcher + docs"
```
Expected: full suite passes; ruff clean.

---

## Self-Review (completed by plan author)

**Spec coverage** — every Phase 4a spec section maps to a task:
- §2 decisions (deep-link direction, daily+on-demand, roles, deep-link redemption point) → Tasks 2,4,5,6,7
- §3 models (ReferralToken, Guardianship) → Task 1
- §4 services (referral, reports) → Tasks 2,3
- §5 handlers (/parent, /teacher, deep-link redeem, /report) → Tasks 4,5,6
- §6 schedule (dispatch_guardian_reports crontab) → Task 7
- §7 tests → each task ships tests; sender/edges mocked
- §8 config (GUARDIAN_REPORT_HOUR, BOT_USERNAME) → Task 1
- §9 DoD → Task 8 gate

**Placeholder scan** — no TBD/TODO. The one cross-phase modification (Phase-1 `cmd_start` gains `command`/`user` params + payload redemption) is explicitly handled with an updated test file in Task 4 so the existing onboarding tests stay green.

**Type/name consistency** — `create_referral_token`/`redeem_token` (T2), `guardian_wards`/`compute_streak`/`build_learner_report` (T3), `send_daily` (Phase 2a) consumed with matching signatures in the handlers (T4-6) and task (T7); patch sites match import sites (`bot.handlers.start.redeem_token`, `bot.handlers.relations.{create_referral_token,guardian_wards,build_learner_report}`, `apps.relations.tasks.{build_learner_report,send_daily}`). `Guardianship.Status.ACTIVE`/`.Role` used consistently. `setup_periodic_tasks` keeps the three interval tasks + adds the crontab one.

**Ordering note** — `docker compose up -d db redis` must be running for the DB-backed tests (Tasks 1,2,3,7). Task 4 modifies Phase-1 code; its updated test file keeps the onboarding suite green.
