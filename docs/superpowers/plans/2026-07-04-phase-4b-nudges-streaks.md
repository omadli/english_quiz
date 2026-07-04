# Faza 4b — Nudges & Streak Motivatsiya Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add motivational nudges (study reminder, pre-exam reminder), streak-milestone celebration, a daily practice quiz-poll, and a `/settings` opt-out toggle — all built on the existing daily-cycle data.

**Architecture:** Idempotency via two new `DailySession` flags (`study_nudged`, `pre_exam_nudged`) and a `LearningProfile.nudges_enabled` opt-out. New `apps/learning/services/nudges.py` holds the due-selection + streak + practice-word logic. Three Celery Beat tasks dispatch the nudges (2 crontab, 1 per-minute interval). The streak celebration hooks into the existing `finalize_exam`; the practice poll reuses `build_questions` + an `is_anonymous` extension to `send_quiz_poll`. Cross-phase touches (`finalize_exam`, `send_quiz_poll`, `/settings`) extend, never break, existing flows.

**Tech Stack:** Django 6 ORM (sync) · Celery + django-celery-beat (crontab + interval) · aiogram 3.x (anonymous quiz poll, settings callback) · pytest + pytest-django.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-04-phase-4b-nudges-streaks-design.md`. Phases 0/1/2a/2b/3/4a complete on `main`.
- Run via uv (not on PATH): `python -m uv run pytest`, `python -m uv run python manage.py ...`. Postgres + Redis via `docker compose up -d db redis`.
- No new models — add fields to `DailySession` (`study_nudged`, `pre_exam_nudged`, both `BooleanField(default=False)`) and `LearningProfile` (`nudges_enabled`, `BooleanField(default=True)`).
- Nudges respect `nudges_enabled`; each nudge type fires at most once per day (the `*_nudged` flags); `blocked_bot` accounts are skipped; sends are best-effort (swallow `TelegramForbiddenError` / log others), matching the Phase-2a/2b sender pattern.
- Practice polls are **anonymous** quiz polls (`is_anonymous=True`) → NO `poll_answer` update → no grading/routing impact.
- Streak celebration fires inside `finalize_exam` AFTER the report send, only when `compute_streak(user)` is in `STREAK_MILESTONES` and `nudges_enabled`. `compute_streak` lives in `apps.relations.services.reports` — import it LOCALLY (inside the function) in learning code to avoid an app-level import cycle.
- Timezone: study/practice fire on a fixed-hour crontab (server TZ = Asia/Tashkent); pre-exam is per-profile-TZ via `is_due_for_pre_exam_nudge` (mirror `is_due_for_exam`).
- Settings: `STUDY_NUDGE_HOUR` (14), `PRACTICE_POLL_HOUR` (12), `PRE_EXAM_NUDGE_MINUTES` (30), `STREAK_MILESTONES` (`[3, 7, 14, 30, 50, 100]`).
- Reuse `send_daily(chat_id, None, [{"caption": text, "image": None, "audio": None}])` for text nudges (no new sender needed).
- TDD; pristine output. Commit footer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

### Prerequisite (once, before Task 1)

```bash
git checkout main && git checkout -b phase-4b-nudges-streaks
```

---

### Task 1: Model fields + settings + migrations

**Files:**
- Modify: `apps/learning/models.py` (add 2 fields to `DailySession`, 1 to `LearningProfile`)
- Modify: `config/settings/base.py` (4 settings)
- Create (generated): `apps/learning/migrations/000X_nudge_fields.py`
- Create: `apps/learning/tests/test_nudge_fields.py`

**Interfaces:**
- Produces: `DailySession.study_nudged`, `DailySession.pre_exam_nudged` (bool, default False); `LearningProfile.nudges_enabled` (bool, default True); settings `STUDY_NUDGE_HOUR`, `PRACTICE_POLL_HOUR`, `PRE_EXAM_NUDGE_MINUTES`, `STREAK_MILESTONES`.

- [ ] **Step 1: Write the failing test**

`apps/learning/tests/test_nudge_fields.py`:
```python
import pytest

from apps.accounts.models import User
from apps.learning.models import DailySession, LearningProfile

pytestmark = pytest.mark.django_db


def test_nudge_defaults():
    u = User.objects.create(first_name="U")
    profile = LearningProfile.objects.create(user=u)
    assert profile.nudges_enabled is True
    session = DailySession.objects.create(user=u, date="2026-07-04")
    assert session.study_nudged is False
    assert session.pre_exam_nudged is False


def test_settings_present(settings):
    assert isinstance(settings.STUDY_NUDGE_HOUR, int)
    assert isinstance(settings.PRACTICE_POLL_HOUR, int)
    assert isinstance(settings.PRE_EXAM_NUDGE_MINUTES, int)
    assert isinstance(settings.STREAK_MILESTONES, list)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_nudge_fields.py -v`
Expected: FAIL — fields/settings missing.

- [ ] **Step 3: Add the model fields**

In `apps/learning/models.py`, add to `LearningProfile` (after `is_active`):
```python
    nudges_enabled = models.BooleanField(default=True)
```
Add to `DailySession` (after `total`):
```python
    study_nudged = models.BooleanField(default=False)
    pre_exam_nudged = models.BooleanField(default=False)
```

- [ ] **Step 4: Add settings**

In `config/settings/base.py`, near the other learning settings, add:
```python
STUDY_NUDGE_HOUR = env.int("STUDY_NUDGE_HOUR", default=14)
PRACTICE_POLL_HOUR = env.int("PRACTICE_POLL_HOUR", default=12)
PRE_EXAM_NUDGE_MINUTES = env.int("PRE_EXAM_NUDGE_MINUTES", default=30)
STREAK_MILESTONES = env.list("STREAK_MILESTONES", cast=int, default=[3, 7, 14, 30, 50, 100])
```

- [ ] **Step 5: Make migrations + run tests**

Run:
```bash
python -m uv run python manage.py makemigrations learning
python -m uv run python manage.py migrate
python -m uv run pytest apps/learning/tests/test_nudge_fields.py -v
```
Expected: migration created; 2 tests PASS.

- [ ] **Step 6: Full suite + ruff + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning config/settings/base.py
git commit -m "feat(learning): nudge/streak model fields + settings"
```
Expected: full suite passes (173 prior + 2 new = 175); ruff clean.

---

### Task 2: Nudge due-selection + streak-message services

**Files:**
- Create: `apps/learning/services/nudges.py`
- Modify: `bot/strings.py`
- Create: `apps/learning/tests/test_nudges_service.py`

**Interfaces:**
- Consumes: `DailySession`, `LearningProfile`, settings `PRE_EXAM_NUDGE_MINUTES`/`STREAK_MILESTONES`.
- Produces:
  - `due_study_nudges(today) -> list[DailySession]`
  - `is_due_for_pre_exam_nudge(profile, now_utc) -> bool`
  - `due_pre_exam_nudges(now_utc) -> list[DailySession]`
  - `mark_study_nudged(session)` / `mark_pre_exam_nudged(session)`
  - `streak_milestone_message(streak) -> str | None`
  - strings `NUDGE_STUDY`, `NUDGE_PRE_EXAM`, `NUDGE_STREAK` (the last uses `{streak}`).

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_nudges_service.py`:
```python
import datetime
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.learning.models import DailySession, LearningProfile
from apps.learning.services.nudges import (
    due_study_nudges,
    is_due_for_pre_exam_nudge,
    mark_study_nudged,
    streak_milestone_message,
)

pytestmark = pytest.mark.django_db


def _learner(**profile_kw):
    u = User.objects.create(first_name="U")
    LearningProfile.objects.create(user=u, onboarded=True, **profile_kw)
    return u


def test_due_study_nudges_selects_delivered_enabled_unnudged():
    today = timezone.localdate()
    u1 = _learner()  # nudges on
    s1 = DailySession.objects.create(user=u1, date=today, status=DailySession.Status.DELIVERED)
    u2 = _learner(nudges_enabled=False)
    DailySession.objects.create(user=u2, date=today, status=DailySession.Status.DELIVERED)
    u3 = _learner()
    DailySession.objects.create(user=u3, date=today, status=DailySession.Status.COMPLETED)
    u4 = _learner()
    DailySession.objects.create(user=u4, date=today, status=DailySession.Status.DELIVERED,
                                study_nudged=True)
    due = due_study_nudges(today)
    ids = {s.id for s in due}
    assert s1.id in ids
    assert len(ids) == 1  # only u1


def test_mark_study_nudged_persists():
    u = _learner()
    s = DailySession.objects.create(user=u, date=timezone.localdate(),
                                    status=DailySession.Status.DELIVERED)
    mark_study_nudged(s)
    s.refresh_from_db()
    assert s.study_nudged is True


def test_is_due_for_pre_exam_nudge_window():
    # exam at 20:00 Tashkent, PRE_EXAM_NUDGE_MINUTES=30 → due at 19:30 local
    u = _learner(exam_time=datetime.time(20, 0), timezone="Asia/Tashkent",
                 study_weekdays=[0, 1, 2, 3, 4, 5, 6])
    profile = u.learning_profile
    tz = ZoneInfo("Asia/Tashkent")
    due_local = datetime.datetime(2026, 7, 6, 19, 30, tzinfo=tz)  # a Monday
    assert is_due_for_pre_exam_nudge(profile, due_local.astimezone(datetime.timezone.utc)) is True
    off_local = datetime.datetime(2026, 7, 6, 18, 0, tzinfo=tz)
    assert is_due_for_pre_exam_nudge(profile, off_local.astimezone(datetime.timezone.utc)) is False


def test_streak_milestone_message():
    assert streak_milestone_message(7) is not None
    assert "7" in streak_milestone_message(7)
    assert streak_milestone_message(8) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_nudges_service.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Add strings**

In `bot/strings.py`, add:
```python
NUDGE_STUDY = "📚 So'zlarni takrorlayapsizmi? Kechqurun imtihon bor — tayyorlaning! 💪"
NUDGE_PRE_EXAM = "⏰ Imtihon vaqti yaqinlashdi! Tayyor bo'ling. 📝"
NUDGE_STREAK = "🔥 <b>{streak} kunlik streak!</b> Zo'r ketyapsiz, barakalla! 🎉"
```

- [ ] **Step 4: Implement `apps/learning/services/nudges.py`**

```python
import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from apps.learning.models import DailySession, LearningProfile
from bot import strings


def due_study_nudges(today) -> list[DailySession]:
    return list(
        DailySession.objects.filter(
            date=today,
            status=DailySession.Status.DELIVERED,
            study_nudged=False,
            user__learning_profile__nudges_enabled=True,
        ).select_related("user__telegram")
    )


def is_due_for_pre_exam_nudge(profile: LearningProfile, now_utc: datetime.datetime) -> bool:
    if not profile.is_active or not profile.onboarded:
        return False
    local = now_utc.astimezone(ZoneInfo(profile.timezone))
    if local.weekday() not in profile.study_weekdays:
        return False
    exam_dt = local.replace(
        hour=profile.exam_time.hour, minute=profile.exam_time.minute, second=0, microsecond=0
    )
    target = exam_dt - datetime.timedelta(minutes=settings.PRE_EXAM_NUDGE_MINUTES)
    return local.hour == target.hour and local.minute == target.minute


def due_pre_exam_nudges(now_utc: datetime.datetime) -> list[DailySession]:
    today = now_utc.astimezone(ZoneInfo("Asia/Tashkent")).date()
    candidates = DailySession.objects.filter(
        date=today,
        status=DailySession.Status.DELIVERED,
        pre_exam_nudged=False,
        user__learning_profile__nudges_enabled=True,
    ).select_related("user__telegram", "user__learning_profile")
    return [s for s in candidates if is_due_for_pre_exam_nudge(s.user.learning_profile, now_utc)]


def mark_study_nudged(session: DailySession) -> None:
    DailySession.objects.filter(id=session.id).update(study_nudged=True)


def mark_pre_exam_nudged(session: DailySession) -> None:
    DailySession.objects.filter(id=session.id).update(pre_exam_nudged=True)


def streak_milestone_message(streak: int) -> str | None:
    if streak in settings.STREAK_MILESTONES:
        return strings.NUDGE_STREAK.format(streak=streak)
    return None
```
Note: the `due_pre_exam_nudges` `today` uses the profile's local date; since all profiles default to Asia/Tashkent this is correct for the common case (per-profile-date refinement is deferred).

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_nudges_service.py -v`
Expected: all PASS.

- [ ] **Step 6: Full suite + ruff + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/services/nudges.py apps/learning/tests/test_nudges_service.py bot/strings.py
git commit -m "feat(learning): nudge due-selection + streak-message services"
```

---

### Task 3: Practice-word service + anonymous quiz poll

**Files:**
- Modify: `apps/learning/services/nudges.py` (add `pick_practice_word`, `active_practice_learners`)
- Modify: `bot/sender.py` (`send_quiz_poll` gains `is_anonymous`)
- Modify: `apps/learning/tests/test_nudges_service.py` (practice tests)
- Create: `bot/tests/test_sender_anonymous.py`

**Interfaces:**
- Consumes: `WordProgress`, `Word`.
- Produces: `pick_practice_word(learner) -> Word | None`; `active_practice_learners() -> list[User]`; `send_quiz_poll(chat_id, question, options, correct_option, explanation=None, is_anonymous=False) -> str`.

- [ ] **Step 1: Write the failing tests**

Add to `apps/learning/tests/test_nudges_service.py`:
```python
def test_pick_practice_word_and_active_learners():
    from apps.catalog.models import Book, Unit, Word
    from apps.learning.models import WordProgress
    from apps.learning.services.nudges import active_practice_learners, pick_practice_word

    book = Book.objects.create(number=1, title="B1")
    unit = Unit.objects.create(book=book, number=1, title="U1")
    word = Word.objects.create(unit=unit, en="apple", uz="olma")
    u = _learner()
    assert pick_practice_word(u) is None  # no progress yet
    assert u not in active_practice_learners()
    WordProgress.objects.create(user=u, word=word)
    assert pick_practice_word(u) == word
    assert u in active_practice_learners()
```

`bot/tests/test_sender_anonymous.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot import sender

pytestmark = pytest.mark.asyncio


@patch("bot.sender._make_bot")
async def test_send_quiz_poll_anonymous_flag(mock_make_bot):
    bot = AsyncMock()
    msg = MagicMock()
    msg.poll.id = "PID"
    bot.send_poll.return_value = msg
    mock_make_bot.return_value = bot
    # sync wrapper; call in a thread to avoid nested-loop issues
    import asyncio
    poll_id = await asyncio.to_thread(
        sender.send_quiz_poll, 42, "Q", ["a", "b"], 0, "expl", True
    )
    assert poll_id == "PID"
    assert bot.send_poll.call_args.kwargs["is_anonymous"] is True
```
(If `asyncio.to_thread` around the `asyncio.run`-based wrapper proves awkward under pytest-asyncio, make this a plain sync `def test_...` without the `asyncio` marker and call `sender.send_quiz_poll(...)` directly — the point is to assert `is_anonymous=True` reaches `bot.send_poll`.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_nudges_service.py::test_pick_practice_word_and_active_learners bot/tests/test_sender_anonymous.py -v`
Expected: FAIL — functions / param missing.

- [ ] **Step 3: Add practice services to `apps/learning/services/nudges.py`**

Add imports at top (with the existing ones):
```python
import random

from apps.accounts.models import User
from apps.catalog.models import Word
from apps.learning.models import WordProgress
```
Add functions:
```python
def pick_practice_word(learner) -> Word | None:
    word_ids = list(
        WordProgress.objects.filter(user=learner).values_list("word_id", flat=True)
    )
    if not word_ids:
        return None
    return Word.objects.get(pk=random.choice(word_ids))


def active_practice_learners() -> list:
    return list(
        User.objects.filter(
            learning_profile__nudges_enabled=True, word_progress__isnull=False
        ).distinct()
    )
```

- [ ] **Step 4: Extend `send_quiz_poll` in `bot/sender.py`**

Add `is_anonymous: bool = False` to both `_send_quiz_poll` and `send_quiz_poll`, and thread it through:
```python
async def _send_quiz_poll(
    bot: Bot,
    chat_id: int,
    question: str,
    options: list[str],
    correct_option: int,
    explanation: str | None = None,
    is_anonymous: bool = False,
) -> str:
    msg = await bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=options,
        type=PollType.QUIZ,
        correct_option_id=correct_option,
        is_anonymous=is_anonymous,
        explanation=explanation,
    )
    return msg.poll.id


def send_quiz_poll(
    chat_id: int,
    question: str,
    options: list[str],
    correct_option: int,
    explanation: str | None = None,
    is_anonymous: bool = False,
) -> str:
    async def _run() -> str:
        bot = _make_bot()
        try:
            return await _send_quiz_poll(
                bot, chat_id, question, options, correct_option, explanation, is_anonymous
            )
        finally:
            await bot.session.close()

    return asyncio.run(_run())
```
(The Phase-2b exam caller passes no `is_anonymous`, so it keeps the exam default `False` — non-anonymous — unchanged.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_nudges_service.py bot/tests/test_sender_anonymous.py -v`
Expected: all PASS.

- [ ] **Step 6: Full suite + ruff + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/services/nudges.py apps/learning/tests/test_nudges_service.py bot/sender.py bot/tests/test_sender_anonymous.py
git commit -m "feat(learning): practice-word picker + anonymous quiz-poll param"
```

---

### Task 4: Streak celebration in `finalize_exam`

**Files:**
- Modify: `apps/learning/services/report.py` (`finalize_exam`)
- Modify: `apps/learning/tests/` (add a streak-hook test — create `apps/learning/tests/test_finalize_streak.py`)

**Interfaces:**
- Consumes: `streak_milestone_message` (Task 2), `compute_streak` (Phase 4a, `apps.relations.services.reports`), `send_daily`.
- Produces: `finalize_exam` sends an extra celebration message when the post-completion streak is a milestone and the user has `nudges_enabled`.

- [ ] **Step 1: Write the failing test**

`apps/learning/tests/test_finalize_streak.py`:
```python
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import TelegramAccount, User
from apps.learning.models import DailySession, LearningProfile
from apps.learning.services.report import finalize_exam

pytestmark = pytest.mark.django_db


def _learner(nudges=True):
    u = User.objects.create(first_name="U")
    LearningProfile.objects.create(user=u, onboarded=True, nudges_enabled=nudges)
    TelegramAccount.objects.create(user=u, telegram_id=555)
    return u


@patch("apps.learning.services.report.send_daily")
@patch("apps.learning.services.report.compute_streak", return_value=7)
def test_finalize_sends_streak_celebration_on_milestone(mock_streak, mock_send):
    u = _learner()
    s = DailySession.objects.create(user=u, date=timezone.localdate(),
                                    status=DailySession.Status.EXAM_SENT, total=10)
    finalize_exam(s)
    # one send for the report + one for the streak celebration
    assert mock_send.call_count == 2


@patch("apps.learning.services.report.send_daily")
@patch("apps.learning.services.report.compute_streak", return_value=8)
def test_finalize_no_celebration_when_not_milestone(mock_streak, mock_send):
    u = _learner()
    s = DailySession.objects.create(user=u, date=timezone.localdate(),
                                    status=DailySession.Status.EXAM_SENT, total=10)
    finalize_exam(s)
    assert mock_send.call_count == 1  # report only


@patch("apps.learning.services.report.send_daily")
@patch("apps.learning.services.report.compute_streak", return_value=7)
def test_finalize_no_celebration_when_nudges_disabled(mock_streak, mock_send):
    u = _learner(nudges=False)
    s = DailySession.objects.create(user=u, date=timezone.localdate(),
                                    status=DailySession.Status.EXAM_SENT, total=10)
    finalize_exam(s)
    assert mock_send.call_count == 1  # report only, no celebration
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_finalize_streak.py -v`
Expected: FAIL — no celebration send.

- [ ] **Step 3: Extend `finalize_exam`**

In `apps/learning/services/report.py`, import at top:
```python
from apps.learning.services.nudges import streak_milestone_message
from apps.relations.services.reports import compute_streak
```
(These are safe module-level imports: `nudges` imports only `apps.learning.models` + `bot.strings`; `relations.services.reports` imports only `apps.learning.models` + `apps.relations.models` — neither imports `apps.learning.services.report`, so no cycle. If a cycle ever surfaces at import time, move these two imports inside `finalize_exam`.)

At the END of `finalize_exam`, after the report-send `try/except` block, add:
```python
    if not account.blocked_bot and getattr(session.user, "learning_profile", None) \
            and session.user.learning_profile.nudges_enabled:
        message = streak_milestone_message(compute_streak(session.user))
        if message:
            try:
                send_daily(account.telegram_id, None,
                           [{"caption": message, "image": None, "audio": None}])
            except Exception as exc:  # best-effort celebration
                logger.warning("failed to send streak celebration for %s: %s", session.id, exc)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_finalize_streak.py apps/learning/tests/ -k "exam or report or finalize" -v`
Expected: new tests PASS; existing finalize/report tests still PASS.

- [ ] **Step 5: Full suite + ruff + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/services/report.py apps/learning/tests/test_finalize_streak.py
git commit -m "feat(learning): streak-milestone celebration in finalize_exam"
```

---

### Task 5: Dispatch tasks + Beat registration

**Files:**
- Modify: `apps/learning/tasks.py`
- Modify: `apps/learning/management/commands/setup_periodic_tasks.py`
- Create: `apps/learning/tests/test_nudge_tasks.py`
- Modify: `apps/learning/tests/test_setup_periodic_tasks.py`

**Interfaces:**
- Consumes: `due_study_nudges`/`due_pre_exam_nudges`/`mark_*`/`pick_practice_word`/`active_practice_learners` (Tasks 2-3), `build_questions` (Phase 2b), `send_daily`/`send_quiz_poll` (sender).
- Produces: `dispatch_study_nudges()`, `dispatch_pre_exam_nudges()`, `dispatch_practice_polls()`; three new Beat registrations.

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_nudge_tasks.py`:
```python
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import TelegramAccount, User
from apps.learning.models import DailySession, LearningProfile
from apps.learning.tasks import dispatch_practice_polls, dispatch_study_nudges

pytestmark = pytest.mark.django_db


def _learner(tid, nudges=True):
    u = User.objects.create(first_name="U")
    LearningProfile.objects.create(user=u, onboarded=True, nudges_enabled=nudges)
    TelegramAccount.objects.create(user=u, telegram_id=tid)
    return u


@patch("apps.learning.tasks.send_daily")
def test_dispatch_study_nudges_sends_and_marks(mock_send):
    u = _learner(101)
    s = DailySession.objects.create(user=u, date=timezone.localdate(),
                                    status=DailySession.Status.DELIVERED)
    dispatch_study_nudges()
    assert mock_send.call_count == 1
    assert mock_send.call_args.args[0] == 101
    s.refresh_from_db()
    assert s.study_nudged is True


@patch("apps.learning.tasks.send_quiz_poll")
@patch("apps.learning.tasks.build_questions")
@patch("apps.learning.tasks.pick_practice_word")
@patch("apps.learning.tasks.active_practice_learners")
def test_dispatch_practice_polls_sends_anonymous(mock_learners, mock_pick, mock_build, mock_poll):
    u = _learner(202)
    mock_learners.return_value = [u]
    mock_pick.return_value = object()
    mock_build.return_value = [
        {"prompt": "Q", "options": ["a", "b"], "correct_option": 0, "explanation": "x"}
    ]
    dispatch_practice_polls()
    assert mock_poll.call_count == 1
    assert mock_poll.call_args.kwargs.get("is_anonymous") is True
```

Add to `apps/learning/tests/test_setup_periodic_tasks.py`:
```python
def test_setup_registers_nudge_tasks():
    from django_celery_beat.models import PeriodicTask

    call_command("setup_periodic_tasks")
    for name in ("dispatch_study_nudges", "dispatch_pre_exam_nudges", "dispatch_practice_polls"):
        assert PeriodicTask.objects.filter(name=name).count() == 1
    # existing tasks intact
    assert PeriodicTask.objects.filter(name="dispatch_morning_deliveries").exists()
    assert PeriodicTask.objects.filter(name="dispatch_guardian_reports").exists()
    # idempotent
    call_command("setup_periodic_tasks")
    assert PeriodicTask.objects.filter(name="dispatch_study_nudges").count() == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_nudge_tasks.py apps/learning/tests/test_setup_periodic_tasks.py -v`
Expected: FAIL — tasks / registrations missing.

- [ ] **Step 3: Add the tasks to `apps/learning/tasks.py`**

Add imports:
```python
from apps.learning.services.exam import build_questions
from apps.learning.services.nudges import (
    active_practice_learners,
    due_pre_exam_nudges,
    due_study_nudges,
    mark_pre_exam_nudged,
    mark_study_nudged,
    pick_practice_word,
)
from bot import strings
from bot.sender import send_daily, send_quiz_poll
```
Add a small helper + the three tasks:
```python
def _send_text(telegram_id: int, text: str) -> None:
    send_daily(telegram_id, None, [{"caption": text, "image": None, "audio": None}])


@shared_task
def dispatch_study_nudges() -> None:
    for session in due_study_nudges(timezone.localdate()):
        account = getattr(session.user, "telegram", None)
        if account is None or account.blocked_bot:
            continue
        try:
            _send_text(account.telegram_id, strings.NUDGE_STUDY)
        except Exception:  # best-effort
            pass
        mark_study_nudged(session)


@shared_task
def dispatch_pre_exam_nudges() -> None:
    for session in due_pre_exam_nudges(timezone.now()):
        account = getattr(session.user, "telegram", None)
        if account is None or account.blocked_bot:
            continue
        try:
            _send_text(account.telegram_id, strings.NUDGE_PRE_EXAM)
        except Exception:  # best-effort
            pass
        mark_pre_exam_nudged(session)


@shared_task
def dispatch_practice_polls() -> None:
    for learner in active_practice_learners():
        account = getattr(learner, "telegram", None)
        if account is None or account.blocked_bot:
            continue
        word = pick_practice_word(learner)
        if word is None:
            continue
        q = build_questions([word])[0]
        try:
            send_quiz_poll(
                account.telegram_id, q["prompt"], q["options"], q["correct_option"],
                q["explanation"], is_anonymous=True,
            )
        except Exception:  # best-effort
            pass
```
Note: mark AFTER attempting the send (even if the send fails) so a persistently-failing account isn't retried every crontab tick — matches the "at most once per day" intent.

- [ ] **Step 4: Register the Beat tasks**

In `apps/learning/management/commands/setup_periodic_tasks.py`, add to the interval `tasks` dict:
```python
            "dispatch_pre_exam_nudges": "apps.learning.tasks.dispatch_pre_exam_nudges",
```
And after the guardian crontab registration, register the two daily crontabs:
```python
        study_cron, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour=str(settings.STUDY_NUDGE_HOUR),
            day_of_week="*", day_of_month="*", month_of_year="*",
        )
        PeriodicTask.objects.update_or_create(
            name="dispatch_study_nudges",
            defaults={"crontab": study_cron, "interval": None,
                      "task": "apps.learning.tasks.dispatch_study_nudges"},
        )
        practice_cron, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour=str(settings.PRACTICE_POLL_HOUR),
            day_of_week="*", day_of_month="*", month_of_year="*",
        )
        PeriodicTask.objects.update_or_create(
            name="dispatch_practice_polls",
            defaults={"crontab": practice_cron, "interval": None,
                      "task": "apps.learning.tasks.dispatch_practice_polls"},
        )
```
(`dispatch_pre_exam_nudges` rides the existing 60s `schedule` via the interval `tasks` dict loop.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_nudge_tasks.py apps/learning/tests/test_setup_periodic_tasks.py -v`
Expected: all PASS.

- [ ] **Step 6: Full suite + ruff + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/tasks.py apps/learning/management/commands/setup_periodic_tasks.py apps/learning/tests/test_nudge_tasks.py apps/learning/tests/test_setup_periodic_tasks.py
git commit -m "feat(learning): nudge/practice dispatch tasks + Beat registration"
```

---

### Task 6: `/settings` nudge toggle

**Files:**
- Modify: `bot/handlers/settings.py` (`format_profile`, new `set:nudges` handler)
- Modify: `bot/keyboards/settings.py`
- Modify: `bot/strings.py`
- Create: `bot/tests/test_settings_nudges.py`

**Interfaces:**
- Consumes: `LearningProfile.nudges_enabled`.
- Produces: a `set:nudges` toggle handler that flips `nudges_enabled` and re-renders; `settings_keyboard()` gains the toggle button.

- [ ] **Step 1: Write the failing test**

`bot/tests/test_settings_nudges.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import settings as settings_handler

pytestmark = pytest.mark.asyncio


@patch("bot.handlers.settings.sync_to_async")
async def test_toggle_nudges_flips_and_rerenders(mock_sta):
    # sync_to_async(fn) -> returns an async callable that just runs fn
    def _wrap(fn):
        async def _inner(*a, **k):
            return fn(*a, **k)
        return _inner
    mock_sta.side_effect = _wrap

    profile = MagicMock()
    profile.nudges_enabled = True
    profile.study_weekdays = [0, 1, 2]
    profile.audio_enabled = True
    callback = AsyncMock()
    await settings_handler.toggle_nudges(callback, profile=profile)
    assert profile.nudges_enabled is False  # flipped
    callback.message.edit_text.assert_awaited()
```
(If mocking `sync_to_async` proves awkward, instead make this a `@pytest.mark.django_db` async test with a real `User`+`LearningProfile` and assert `profile.nudges_enabled` flipped after `refresh_from_db()` — the point is the flip + re-render.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_settings_nudges.py -v`
Expected: FAIL — `toggle_nudges` missing.

- [ ] **Step 3: Add strings + keyboard button**

In `bot/strings.py`, add:
```python
SETTINGS_NUDGES = "Eslatmalar"
BTN_NUDGES_ON = "🔔 Yoqilgan"
BTN_NUDGES_OFF = "🔕 O'chirilgan"
```
In `bot/keyboards/settings.py`, add a row to `settings_keyboard()`:
```python
        [InlineKeyboardButton(text=f"🔔 {strings.SETTINGS_NUDGES}", callback_data="set:nudges")],
```

- [ ] **Step 4: Add the toggle handler + show state in `format_profile`**

In `bot/handlers/settings.py`, add imports:
```python
from asgiref.sync import sync_to_async
```
In `format_profile`, add a nudges line (before the blank line + edit hint):
```python
    nudges = strings.BTN_NUDGES_ON if profile.nudges_enabled else strings.BTN_NUDGES_OFF
```
and include `f"• {strings.SETTINGS_NUDGES}: <b>{nudges}</b>",` in the returned list (after the audio line).

Add the handler:
```python
@router.callback_query(F.data == "set:nudges")
async def toggle_nudges(callback: CallbackQuery, profile: LearningProfile) -> None:
    await callback.answer()
    profile.nudges_enabled = not profile.nudges_enabled
    await sync_to_async(profile.save)(update_fields=["nudges_enabled", "updated_at"])
    await callback.message.edit_text(format_profile(profile), reply_markup=settings_keyboard())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_settings_nudges.py bot/tests/ -k settings -v`
Expected: new test PASS; existing settings tests still PASS (the added keyboard row / profile line don't break them — if an existing test asserts an exact keyboard length or profile string, update it to include the new row/line).

- [ ] **Step 6: Full suite + ruff + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/handlers/settings.py bot/keyboards/settings.py bot/strings.py bot/tests/test_settings_nudges.py
git commit -m "feat(bot): /settings nudge on/off toggle"
```

---

### Task 7: Docs + final gate

**Files:**
- Modify: `Readme.md`

**Interfaces:**
- Produces: Readme documents the motivation features + the new setup step.

- [ ] **Step 1: Update `Readme.md`**

Add a "Motivation & streaks" subsection under the Bot section:
```markdown
## Motivation & streaks

The bot nudges learners during the day: a study reminder (`STUDY_NUDGE_HOUR`),
a pre-exam reminder (`PRE_EXAM_NUDGE_MINUTES` before each learner's exam), a
streak celebration when a completed exam hits a `STREAK_MILESTONES` day count,
and a daily anonymous practice quiz-poll (`PRACTICE_POLL_HOUR`). Learners can
turn all of this off from `/settings`. (Re-run `setup_periodic_tasks` after
migrating to register the new Beat jobs.)
```

- [ ] **Step 2: Final gate**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check .
```
Expected: full suite passes; ruff clean whole-repo.

- [ ] **Step 3: Commit**

```bash
git add Readme.md
git commit -m "docs: document motivation & streak features"
```

---

## Self-Review (completed by plan author)

**Spec coverage** — every Phase 4b spec section maps to a task:
- §3 model fields (DailySession flags, nudges_enabled) → Task 1
- §4 services (due_study/pre_exam, marks, streak message, practice word, active learners) → Tasks 2, 3
- §5 sender/finalize (anonymous poll param, streak hook) → Tasks 3, 4
- §6 dispatch tasks + Beat → Task 5
- §7 /settings toggle → Task 6
- §8 tests → each task ships tests; sender mocked
- §9 config → Task 1
- §10 DoD → Task 7 gate

**Placeholder scan** — no TBD/TODO. Cross-phase modifications (`send_quiz_poll` +param, `finalize_exam` +hook, `/settings` +toggle) each keep the existing default/flow and ship a test; where an existing test might assert an exact keyboard length or profile string, Task 6 Step 5 flags updating it.

**Type/name consistency** — `due_study_nudges`/`due_pre_exam_nudges`/`is_due_for_pre_exam_nudge`/`mark_study_nudged`/`mark_pre_exam_nudged`/`streak_milestone_message`/`pick_practice_word`/`active_practice_learners` (Tasks 2-3) consumed with matching names in tasks (Task 5); patch sites match import sites (`apps.learning.tasks.*`, `apps.learning.services.report.{send_daily,compute_streak}`). `send_quiz_poll(..., is_anonymous=False)` default preserves the Phase-2b exam call. `build_questions([word])[0]` dict keys (`prompt`/`options`/`correct_option`/`explanation`) match `exam.py`'s `_question_for`. `setup_periodic_tasks` keeps the 3 interval + 1 guardian-crontab tasks and adds pre-exam (interval) + study/practice (crontab).

**Import-cycle check** — `nudges.py` imports `apps.learning.models` + `bot.strings` + `apps.catalog.models` + `apps.accounts.models`; `report.py` adds imports of `nudges.streak_milestone_message` and `relations.services.reports.compute_streak`. `relations.services.reports` imports only `apps.learning.models` + `apps.relations.models` (not `apps.learning.services.report`), so no cycle. Fallback (move imports inside `finalize_exam`) documented in Task 4 Step 3.

**Ordering note** — `docker compose up -d db redis` for DB tests (Tasks 1-5). Task 4 modifies Phase-2b `finalize_exam`; Task 6 modifies Phase-1 `/settings`; both keep existing suites green (flagged in-task).
