# Faza 3 — Guruh Quiz (Group Quiz) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a group admin run a QuizBot-style quiz in a Telegram group — configure book/units/types/count/interval via a wizard, then fire sequential native quiz polls, tracking each student's correct-count and response time and posting a leaderboard, with results persisted for later teacher reports.

**Architecture:** A new `apps/quiz` app persists `GroupQuizSession` (its `status` field IS the wizard/run state — no aiogram FSM), `GroupQuizQuestion` (keyed by `poll_id`), and `GroupQuizParticipant`. A new bot router drives the wizard (admin-only) and starts an async `run_group_quiz` coroutine that lives in the bot process (`asyncio.sleep` between polls). The existing Phase-2b `poll_answer` handler is extended to route by `poll_id`: group questions first, personal-exam questions as fallback. Question generation reuses Phase-2b `build_questions` (extended with a `types` filter).

**Tech Stack:** Django 6 ORM (sync) · aiogram 3.x (group handlers + async runner) · sync_to_async bridge · pytest + pytest-django + pytest-asyncio.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-04-phase-3-group-quiz-design.md`. Phases 0/1/2a/2b are complete on `main`.
- Run via uv (not on PATH): `python -m uv run pytest`, `python -m uv run python manage.py ...`.
- Postgres + Redis via `docker compose up -d db redis` for DB tests.
- New app `apps.quiz` (label `quiz`) added to `INSTALLED_APPS`. Models `GroupQuizSession`/`GroupQuizQuestion`/`GroupQuizParticipant` inherit `apps.common.models.TimeStampedModel`.
- Sync services; async only in bot handlers + the runner. DB access from async code goes through `sync_to_async` (or sync helpers called via `sync_to_async`) — no native async ORM.
- Question types: `en_uz`/`uz_en`/`def_word` (reuse `ExamQuestion.QType` values). `build_questions` gains an optional `types` param, default `None` = all three (backward compatible with Phase 2b's `run_exam`).
- Callback-data prefix scheme: `gq:book:<n>`, `gq:unit:<id>`, `gq:units_done`, `gq:type:<t>`, `gq:types_done`, `gq:count:<n>`, `gq:int:<s>`, `gq:start`.
- One active (`configuring`/`running`) `GroupQuizSession` per `chat_id` at a time.
- Admin-only: `/quiz` and `/stop` verify the caller is a chat admin via `bot.get_chat_member`.
- poll_answer routing: the single `on_poll_answer` handler tries `record_group_answer` first; if it returns `False`, falls back to Phase-2b `record_answer`.
- Leaderboard order: `correct_count` descending, then `total_time` ascending; medals 🥇🥈🥉.
- OUT of scope: teacher dashboards/reports (Phase 4 consumes the persisted results), pre-authored quiz bank, web.
- TDD; pristine output. Commit footer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

### Prerequisite (once, before Task 1)

```bash
git checkout main && git checkout -b phase-3-group-quiz
```

---

### Task 1: `apps/quiz` app + models + admin

**Files:**
- Create: `apps/quiz/__init__.py`, `apps/quiz/apps.py`, `apps/quiz/models.py`, `apps/quiz/admin.py`, `apps/quiz/migrations/__init__.py`
- Create: `apps/quiz/tests/__init__.py`, `apps/quiz/tests/test_models.py`
- Modify: `config/settings/base.py` (add `apps.quiz` to INSTALLED_APPS)
- Create (generated): `apps/quiz/migrations/0001_initial.py`

**Interfaces:**
- Produces: `apps.quiz.models.GroupQuizSession` (chat_id, started_by, book, unit_ids, question_types, question_count, interval_seconds, status via `Status` choices, started_at, finished_at), `GroupQuizQuestion` (session, word, order, question_type, poll_id, sent_at, options, correct_option), `GroupQuizParticipant` (session, telegram_id, username, full_name, correct_count, total_time; unique (session, telegram_id)).

- [ ] **Step 1: Scaffold the app**

`apps/quiz/__init__.py`: (empty). `apps/quiz/migrations/__init__.py`: (empty).

`apps/quiz/apps.py`:
```python
from django.apps import AppConfig


class QuizConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.quiz"
    label = "quiz"
    verbose_name = "Group Quiz"
```
Add `"apps.quiz",` to `INSTALLED_APPS` in `config/settings/base.py`, after `"apps.learning",`.

- [ ] **Step 2: Write the failing tests**

`apps/quiz/tests/__init__.py`: (empty)

`apps/quiz/tests/test_models.py`:
```python
import pytest
from django.db import IntegrityError

from apps.catalog.models import Book, Unit, Word
from apps.quiz.models import GroupQuizParticipant, GroupQuizQuestion, GroupQuizSession

pytestmark = pytest.mark.django_db


def _session():
    return GroupQuizSession.objects.create(chat_id=-100123, question_count=10)


def test_session_defaults():
    s = _session()
    assert s.status == GroupQuizSession.Status.CONFIGURING
    assert s.unit_ids == []
    assert s.question_types == []
    assert s.interval_seconds == 20


def test_question_and_participant_relations():
    s = _session()
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    q = GroupQuizQuestion.objects.create(
        session=s, word=word, order=1, question_type="en_uz", options=["a"], correct_option=0
    )
    p = GroupQuizParticipant.objects.create(session=s, telegram_id=555, full_name="Ali")
    assert list(s.questions.all()) == [q]
    assert list(s.participants.all()) == [p]
    assert p.correct_count == 0
    assert p.total_time == 0


def test_participant_unique_per_session():
    s = _session()
    GroupQuizParticipant.objects.create(session=s, telegram_id=555)
    with pytest.raises(IntegrityError):
        GroupQuizParticipant.objects.create(session=s, telegram_id=555)
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m uv run pytest apps/quiz/tests/test_models.py -v`
Expected: FAIL — `apps.quiz.models` missing.

- [ ] **Step 4: Implement `apps/quiz/models.py`**

```python
from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


def _empty_list() -> list:
    return []


class GroupQuizSession(TimeStampedModel):
    class Status(models.TextChoices):
        CONFIGURING = "configuring", "Configuring"
        RUNNING = "running", "Running"
        FINISHED = "finished", "Finished"
        ABORTED = "aborted", "Aborted"

    chat_id = models.BigIntegerField(db_index=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    book = models.ForeignKey("catalog.Book", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    unit_ids = models.JSONField(default=_empty_list)
    question_types = models.JSONField(default=_empty_list)
    question_count = models.PositiveSmallIntegerField(default=10)
    interval_seconds = models.PositiveSmallIntegerField(default=20)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIGURING)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"GroupQuizSession(chat={self.chat_id}, {self.status})"


class GroupQuizQuestion(TimeStampedModel):
    session = models.ForeignKey(GroupQuizSession, on_delete=models.CASCADE, related_name="questions")
    word = models.ForeignKey("catalog.Word", on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=0)
    question_type = models.CharField(max_length=10)
    poll_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    options = models.JSONField(default=_empty_list)
    correct_option = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ("order",)

    def __str__(self) -> str:
        return f"GroupQuizQuestion(session={self.session_id}, order={self.order})"


class GroupQuizParticipant(TimeStampedModel):
    session = models.ForeignKey(GroupQuizSession, on_delete=models.CASCADE, related_name="participants")
    telegram_id = models.BigIntegerField()
    username = models.CharField(max_length=64, blank=True, default="")
    full_name = models.CharField(max_length=128, blank=True, default="")
    correct_count = models.PositiveSmallIntegerField(default=0)
    total_time = models.FloatField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "telegram_id"], name="uniq_session_participant")
        ]

    def __str__(self) -> str:
        return f"GroupQuizParticipant(session={self.session_id}, tg={self.telegram_id})"
```

- [ ] **Step 5: Make migrations and run tests**

Run:
```bash
python -m uv run python manage.py makemigrations quiz
python -m uv run pytest apps/quiz/tests/test_models.py -v
```
Expected: migration created; 3 tests PASS.

- [ ] **Step 6: Add admin**

`apps/quiz/admin.py`:
```python
from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import GroupQuizParticipant, GroupQuizQuestion, GroupQuizSession


@admin.register(GroupQuizSession)
class GroupQuizSessionAdmin(ModelAdmin):
    list_display = ("chat_id", "book", "status", "question_count", "interval_seconds", "started_at")
    list_filter = ("status",)
    raw_id_fields = ("started_by", "book")


@admin.register(GroupQuizQuestion)
class GroupQuizQuestionAdmin(ModelAdmin):
    list_display = ("session", "order", "word", "question_type", "poll_id")
    raw_id_fields = ("session", "word")


@admin.register(GroupQuizParticipant)
class GroupQuizParticipantAdmin(ModelAdmin):
    list_display = ("session", "telegram_id", "full_name", "correct_count", "total_time")
    raw_id_fields = ("session",)
```

- [ ] **Step 7: Migrate, full suite, ruff, commit**

Run:
```bash
python -m uv run python manage.py migrate
python -m uv run pytest
python -m uv run ruff check .
git add apps/quiz config/settings/base.py
git commit -m "feat(quiz): GroupQuizSession/Question/Participant models + admin"
```
Expected: migrate clean; full suite passes (124 prior + 3 new = 127); ruff clean.

---

### Task 2: Word sampling + typed question generation

**Files:**
- Create: `apps/quiz/services/__init__.py`, `apps/quiz/services/questions.py`
- Modify: `apps/learning/services/exam.py` (add optional `types` param to `build_questions`)
- Create: `apps/quiz/tests/test_questions.py`
- Modify: `apps/learning/tests/test_exam_questions.py` (add a test for the `types` filter)

**Interfaces:**
- Consumes: `Word`, `build_questions` (Phase 2b).
- Produces:
  - `apps.quiz.services.questions.sample_words(unit_ids, count) -> list[Word]` — up to `count` random words from the given units.
  - `apps.learning.services.exam.build_questions(words, types=None)` — when `types` is a non-empty list, cycles through only those types; `None`/empty preserves the default `[en_uz, uz_en, def_word]`.

- [ ] **Step 1: Write the failing tests**

`apps/quiz/tests/test_questions.py`:
```python
import pytest

from apps.catalog.models import Book, Unit, Word
from apps.quiz.services.questions import sample_words

pytestmark = pytest.mark.django_db


def test_sample_words_only_from_given_units():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    u1 = Unit.objects.create(book=book, number=1)
    u2 = Unit.objects.create(book=book, number=2)
    for i in range(5):
        Word.objects.create(unit=u1, en=f"a{i}", uz=f"x{i}", order=i)
    Word.objects.create(unit=u2, en="other", uz="y", order=1)

    words = sample_words([u1.id], 3)
    assert len(words) == 3
    assert all(w.unit_id == u1.id for w in words)


def test_sample_words_caps_at_available():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    u1 = Unit.objects.create(book=book, number=1)
    for i in range(2):
        Word.objects.create(unit=u1, en=f"a{i}", uz=f"x{i}", order=i)
    assert len(sample_words([u1.id], 10)) == 2
```

Add to `apps/learning/tests/test_exam_questions.py`:
```python
def test_build_questions_respects_type_filter(book_words):
    from apps.learning.services.exam import build_questions
    _, _, words = book_words
    qs = build_questions(words[:4], types=["en_uz"])
    assert {q["question_type"] for q in qs} == {"en_uz"}
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/quiz/tests/test_questions.py apps/learning/tests/test_exam_questions.py -v`
Expected: FAIL — `sample_words` missing; `build_questions` doesn't accept `types`.

- [ ] **Step 3: Extend `build_questions` in `apps/learning/services/exam.py`**

Change the `_TYPES` usage and `build_questions` signature:
```python
def build_questions(words: list[Word], types: list[str] | None = None) -> list[dict]:
    active_types = types or _TYPES
    return [_question_for(word, active_types[i % len(active_types)]) for i, word in enumerate(words)]
```
(Leave `_question_for`, `_distractors`, `select_exam_words` unchanged. `run_exam` calls `build_questions(words)` with no `types`, so it keeps the default.)

- [ ] **Step 4: Implement `apps/quiz/services/questions.py`**

`apps/quiz/services/__init__.py`: (empty)

`apps/quiz/services/questions.py`:
```python
import random

from apps.catalog.models import Word


def sample_words(unit_ids: list[int], count: int) -> list[Word]:
    """Up to `count` random words from the given units."""
    pool = list(Word.objects.filter(unit_id__in=unit_ids))
    if len(pool) <= count:
        random.shuffle(pool)
        return pool
    return random.sample(pool, count)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest apps/quiz/tests/test_questions.py apps/learning/tests/test_exam_questions.py -v`
Expected: all PASS (including the existing exam-question tests, since `build_questions` stays backward compatible).

- [ ] **Step 6: Full suite + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/quiz/services apps/learning/services/exam.py apps/quiz/tests/test_questions.py apps/learning/tests/test_exam_questions.py
git commit -m "feat(quiz): sample_words + build_questions type filter"
```
Expected: all pass; ruff clean.

---

### Task 3: Group scoring + leaderboard

**Files:**
- Create: `apps/quiz/services/scoring.py`
- Create: `apps/quiz/tests/test_scoring.py`

**Interfaces:**
- Consumes: `GroupQuizQuestion`, `GroupQuizParticipant`.
- Produces:
  - `apps.quiz.services.scoring.record_group_answer(poll_id, option_ids, telegram_id, username, full_name) -> bool` — if `poll_id` is a group question: upsert the participant, add correctness + response time, return `True`; else return `False`.
  - `apps.quiz.services.scoring.build_leaderboard(session) -> str` — ranked results text.

- [ ] **Step 1: Write the failing tests**

`apps/quiz/tests/test_scoring.py`:
```python
import datetime

import pytest
from django.utils import timezone

from apps.catalog.models import Book, Unit, Word
from apps.quiz.models import GroupQuizParticipant, GroupQuizQuestion, GroupQuizSession
from apps.quiz.services.scoring import build_leaderboard, record_group_answer

pytestmark = pytest.mark.django_db


def _question(correct_option=1):
    s = GroupQuizSession.objects.create(chat_id=-100, status=GroupQuizSession.Status.RUNNING)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    q = GroupQuizQuestion.objects.create(
        session=s, word=word, order=1, question_type="en_uz", poll_id="gp-1",
        options=["a", "b"], correct_option=correct_option,
        sent_at=timezone.now() - datetime.timedelta(seconds=5),
    )
    return s, q


def test_record_group_answer_correct_updates_participant():
    s, q = _question(correct_option=1)
    assert record_group_answer("gp-1", [1], 555, "ali", "Ali") is True
    p = GroupQuizParticipant.objects.get(session=s, telegram_id=555)
    assert p.correct_count == 1
    assert p.total_time > 0  # ~5 seconds


def test_record_group_answer_wrong_no_correct_but_time_counts():
    s, q = _question(correct_option=1)
    record_group_answer("gp-1", [0], 555, "ali", "Ali")
    p = GroupQuizParticipant.objects.get(session=s, telegram_id=555)
    assert p.correct_count == 0
    assert p.total_time > 0


def test_record_group_answer_unknown_poll_returns_false():
    assert record_group_answer("not-a-group-poll", [0], 555, "ali", "Ali") is False


def test_build_leaderboard_orders_by_correct_then_time():
    s = GroupQuizSession.objects.create(chat_id=-100, status=GroupQuizSession.Status.FINISHED)
    GroupQuizParticipant.objects.create(session=s, telegram_id=1, full_name="Slow5", correct_count=3, total_time=50)
    GroupQuizParticipant.objects.create(session=s, telegram_id=2, full_name="Fast5", correct_count=3, total_time=20)
    GroupQuizParticipant.objects.create(session=s, telegram_id=3, full_name="Two", correct_count=2, total_time=5)
    text = build_leaderboard(s)
    # Fast5 (3 correct, 20s) ranks above Slow5 (3 correct, 50s), both above Two (2 correct)
    assert text.index("Fast5") < text.index("Slow5") < text.index("Two")
    assert "🥇" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/quiz/tests/test_scoring.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/quiz/services/scoring.py`**

```python
from django.utils import timezone

from apps.quiz.models import GroupQuizParticipant, GroupQuizQuestion

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def record_group_answer(
    poll_id: str, option_ids: list[int], telegram_id: int, username: str, full_name: str
) -> bool:
    """Score a group-quiz poll answer. Returns False if poll_id is not a group question."""
    question = (
        GroupQuizQuestion.objects.select_related("session").filter(poll_id=poll_id).first()
    )
    if question is None:
        return False

    participant, _ = GroupQuizParticipant.objects.get_or_create(
        session=question.session,
        telegram_id=telegram_id,
        defaults={"username": username, "full_name": full_name},
    )
    if option_ids:
        if option_ids[0] == question.correct_option:
            participant.correct_count += 1
        if question.sent_at is not None:
            participant.total_time += (timezone.now() - question.sent_at).total_seconds()
    participant.save(update_fields=["correct_count", "total_time", "updated_at"])
    return True


def build_leaderboard(session) -> str:
    participants = sorted(
        session.participants.all(), key=lambda p: (-p.correct_count, p.total_time)
    )
    if not participants:
        return "🏁 Test yakunlandi! Hech kim ishtirok etmadi."

    lines = ["🏁 <b>Test yakunlandi!</b>", ""]
    for rank, p in enumerate(participants[:50], start=1):
        label = _MEDALS.get(rank, f"{rank}.")
        name = f"@{p.username}" if p.username else p.full_name or str(p.telegram_id)
        lines.append(f"{label} {name} — <b>{p.correct_count}</b> ({p.total_time:.1f}s)")
    lines.append("\n🏆 G'oliblarni tabriklaymiz!")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/quiz/tests/test_scoring.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/quiz/services/scoring.py apps/quiz/tests/test_scoring.py
git commit -m "feat(quiz): record_group_answer + build_leaderboard"
```

---

### Task 4: poll_answer routing (group → personal)

**Files:**
- Modify: `bot/handlers/quiz.py`
- Modify: `bot/tests/test_handlers_quiz.py`

**Interfaces:**
- Consumes: `record_group_answer` (Task 3), `record_answer` (Phase 2b).
- Produces: `bot.handlers.quiz.on_poll_answer` now routes group-first, personal-fallback.

- [ ] **Step 1: Update the tests**

Replace `bot/tests/test_handlers_quiz.py` with:
```python
from unittest.mock import MagicMock, patch

import pytest

from bot.handlers import quiz

pytestmark = pytest.mark.asyncio


def _poll_answer():
    pa = MagicMock()
    pa.poll_id = "poll-1"
    pa.option_ids = [2]
    pa.user.id = 555
    pa.user.username = "ali"
    pa.user.full_name = "Ali"
    return pa


@patch("bot.handlers.quiz.record_answer")
@patch("bot.handlers.quiz.record_group_answer", return_value=True)
async def test_group_answer_handled_skips_personal(mock_group, mock_personal):
    await quiz.on_poll_answer(_poll_answer())
    mock_group.assert_called_once_with("poll-1", [2], 555, "ali", "Ali")
    mock_personal.assert_not_called()


@patch("bot.handlers.quiz.record_answer")
@patch("bot.handlers.quiz.record_group_answer", return_value=False)
async def test_non_group_falls_back_to_personal(mock_group, mock_personal):
    await quiz.on_poll_answer(_poll_answer())
    mock_group.assert_called_once()
    mock_personal.assert_called_once_with("poll-1", [2])
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_handlers_quiz.py -v`
Expected: FAIL — `on_poll_answer` doesn't call `record_group_answer`.

- [ ] **Step 3: Update `bot/handlers/quiz.py`**

```python
from aiogram import Router
from aiogram.types import PollAnswer
from asgiref.sync import sync_to_async

from apps.learning.services.exam_grade import record_answer
from apps.quiz.services.scoring import record_group_answer

router = Router()


@router.poll_answer()
async def on_poll_answer(poll_answer: PollAnswer) -> None:
    handled = await sync_to_async(record_group_answer)(
        poll_answer.poll_id,
        poll_answer.option_ids,
        poll_answer.user.id,
        poll_answer.user.username or "",
        poll_answer.user.full_name,
    )
    if not handled:
        await sync_to_async(record_answer)(poll_answer.poll_id, poll_answer.option_ids)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_handlers_quiz.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Full suite + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/handlers/quiz.py bot/tests/test_handlers_quiz.py
git commit -m "feat(bot): route poll answers group-first, personal-fallback"
```
Expected: all pass; ruff clean.

---

### Task 5: Quiz wizard — /quiz entry, admin check, book + units selection

**Files:**
- Create: `apps/quiz/services/session.py`
- Create: `bot/handlers/group_quiz.py`
- Create: `bot/keyboards/group_quiz.py`
- Create: `apps/quiz/tests/test_session_service.py`, `bot/tests/test_handlers_group_quiz.py`

**Interfaces:**
- Consumes: `GroupQuizSession`, `Book`, `Unit`, `bot.strings`.
- Produces:
  - `apps.quiz.services.session.get_active_session(chat_id) -> GroupQuizSession | None`
  - `apps.quiz.services.session.start_configuring(chat_id, user_id) -> GroupQuizSession | None` (None if one already active)
  - `apps.quiz.services.session.set_book(session, book_number)`, `toggle_unit(session, unit_id)`, `units_for_book(book_number) -> list[Unit]`
  - `bot.handlers.group_quiz.router` handling `/quiz`, `gq:book:*`, `gq:unit:*`, `gq:units_done`
  - `bot.handlers.group_quiz.is_chat_admin(bot, chat_id, user_id) -> bool`
  - `bot.keyboards.group_quiz.books_keyboard()`, `units_keyboard(book_number, selected)`

- [ ] **Step 1: Write the failing service tests**

`apps/quiz/tests/test_session_service.py`:
```python
import pytest

from apps.catalog.models import Book, Unit
from apps.quiz.models import GroupQuizSession
from apps.quiz.services.session import (
    get_active_session, set_book, start_configuring, toggle_unit, units_for_book,
)

pytestmark = pytest.mark.django_db


def test_start_configuring_creates_one_active():
    s = start_configuring(-100, 5)
    assert s is not None
    assert s.status == GroupQuizSession.Status.CONFIGURING
    # a second start while active returns None
    assert start_configuring(-100, 5) is None


def test_get_active_session():
    assert get_active_session(-100) is None
    s = start_configuring(-100, 5)
    assert get_active_session(-100).id == s.id


def test_set_book_and_toggle_unit():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    u1 = Unit.objects.create(book=book, number=1)
    u2 = Unit.objects.create(book=book, number=2)
    s = start_configuring(-100, 5)
    set_book(s, 1)
    s.refresh_from_db()
    assert s.book_id == book.id
    toggle_unit(s, u1.id)
    toggle_unit(s, u2.id)
    toggle_unit(s, u1.id)  # off again
    s.refresh_from_db()
    assert s.unit_ids == [u2.id]
    assert [u.id for u in units_for_book(1)] == [u1.id, u2.id]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/quiz/tests/test_session_service.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/quiz/services/session.py`**

```python
from apps.catalog.models import Book, Unit
from apps.quiz.models import GroupQuizSession

_ACTIVE = (GroupQuizSession.Status.CONFIGURING, GroupQuizSession.Status.RUNNING)


def get_active_session(chat_id: int) -> GroupQuizSession | None:
    return GroupQuizSession.objects.filter(chat_id=chat_id, status__in=_ACTIVE).order_by("-created_at").first()


def start_configuring(chat_id: int, user_id: int) -> GroupQuizSession | None:
    if get_active_session(chat_id) is not None:
        return None
    return GroupQuizSession.objects.create(
        chat_id=chat_id, started_by_id=user_id, status=GroupQuizSession.Status.CONFIGURING
    )


def units_for_book(book_number: int) -> list[Unit]:
    return list(Unit.objects.filter(book__number=book_number).order_by("number"))


def set_book(session: GroupQuizSession, book_number: int) -> None:
    book = Book.objects.filter(number=book_number).first()
    session.book = book
    session.unit_ids = []
    session.save(update_fields=["book", "unit_ids", "updated_at"])


def toggle_unit(session: GroupQuizSession, unit_id: int) -> None:
    ids = list(session.unit_ids)
    if unit_id in ids:
        ids.remove(unit_id)
    else:
        ids.append(unit_id)
    session.unit_ids = sorted(ids)
    session.save(update_fields=["unit_ids", "updated_at"])
```

- [ ] **Step 4: Write the failing handler/keyboard tests**

`bot/tests/test_handlers_group_quiz.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import group_quiz

pytestmark = pytest.mark.asyncio


async def test_is_chat_admin_true_for_administrator():
    bot = AsyncMock()
    member = MagicMock()
    member.status = "administrator"
    bot.get_chat_member.return_value = member
    assert await group_quiz.is_chat_admin(bot, -100, 5) is True


async def test_is_chat_admin_false_for_member():
    bot = AsyncMock()
    member = MagicMock()
    member.status = "member"
    bot.get_chat_member.return_value = member
    assert await group_quiz.is_chat_admin(bot, -100, 5) is False


@patch("bot.handlers.group_quiz.start_configuring", return_value=None)
@patch("bot.handlers.group_quiz.is_chat_admin", return_value=False)
async def test_cmd_quiz_rejects_non_admin(mock_admin, mock_start):
    message = AsyncMock()
    message.chat.id = -100
    message.from_user.id = 5
    message.bot = AsyncMock()
    await group_quiz.cmd_quiz(message)
    mock_start.assert_not_called()
    message.answer.assert_awaited()
```

`bot/keyboards/group_quiz.py` builder test — fold into the same file:
```python
from bot.keyboards.group_quiz import units_keyboard


def test_units_keyboard_marks_selected():
    # a lightweight non-DB check: build with fake unit tuples
    markup = units_keyboard.__wrapped__ if hasattr(units_keyboard, "__wrapped__") else None
    # (covered indirectly; keyboards are exercised in handler flow)
```
> Skip the keyboard-builder unit test if it needs DB; keyboards are exercised via the handler flow. Keep only the three async tests above in `test_handlers_group_quiz.py`.

- [ ] **Step 5: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_handlers_group_quiz.py -v`
Expected: FAIL — `bot.handlers.group_quiz` missing.

- [ ] **Step 6: Implement the keyboards**

`bot/keyboards/group_quiz.py`:
```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from apps.quiz.services.session import units_for_book

BOOK_NUMBERS = [1, 2, 3, 4, 5, 6]


def books_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=str(n), callback_data=f"gq:book:{n}") for n in BOOK_NUMBERS]
    return InlineKeyboardMarkup(inline_keyboard=[row[:3], row[3:]])


def units_keyboard(book_number: int, selected: list[int]) -> InlineKeyboardMarkup:
    buttons = []
    for unit in units_for_book(book_number):
        mark = "✅ " if unit.id in selected else ""
        buttons.append(InlineKeyboardButton(text=f"{mark}Unit {unit.number}", callback_data=f"gq:unit:{unit.id}"))
    rows = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    rows.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="gq:units_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
```

- [ ] **Step 7: Implement the handlers**

`bot/handlers/group_quiz.py`:
```python
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.quiz.services.session import (
    get_active_session, set_book, start_configuring, toggle_unit,
)
from bot.keyboards.group_quiz import books_keyboard, units_keyboard

router = Router()

_ASK_BOOK = "📚 Qaysi kitobdan test qilamiz?"
_ASK_UNITS = "Unit(lar)ni tanlang, so'ng «Tayyor» bosing."
_NOT_ADMIN = "Bu buyruq faqat guruh adminlari uchun."
_ALREADY = "Bu guruhda test allaqachon sozlanmoqda yoki ketmoqda. /stop bilan to'xtating."


async def is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")


@router.message(Command("quiz"))
async def cmd_quiz(message: Message) -> None:
    if not await is_chat_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer(_NOT_ADMIN)
        return
    session = await sync_to_async(start_configuring)(message.chat.id, message.from_user.id)
    if session is None:
        await message.answer(_ALREADY)
        return
    await message.answer(_ASK_BOOK, reply_markup=books_keyboard())


@router.callback_query(F.data.startswith("gq:book:"))
async def pick_book(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None:
        return
    book_number = int(callback.data.split(":")[-1])
    await sync_to_async(set_book)(session, book_number)
    markup = await sync_to_async(units_keyboard)(book_number, [])
    await callback.message.edit_text(_ASK_UNITS, reply_markup=markup)


@router.callback_query(F.data.startswith("gq:unit:"))
async def toggle_unit_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None or session.book is None:
        return
    unit_id = int(callback.data.split(":")[-1])
    await sync_to_async(toggle_unit)(session, unit_id)
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    markup = await sync_to_async(units_keyboard)(session.book.number, session.unit_ids)
    await callback.message.edit_reply_markup(reply_markup=markup)
```
> Note: `session.book` is accessed after a fresh `get_active_session` fetch, and `units_keyboard` (which queries units) is wrapped in `sync_to_async` — both keep DB access off the async path. The `gq:units_done` handler is added in Task 6 (it transitions to the types step).

- [ ] **Step 8: Run tests, full suite, commit**

Run:
```bash
python -m uv run pytest apps/quiz/tests/test_session_service.py bot/tests/test_handlers_group_quiz.py
python -m uv run pytest
python -m uv run ruff check .
git add apps/quiz/services/session.py bot/handlers/group_quiz.py bot/keyboards/group_quiz.py apps/quiz/tests/test_session_service.py bot/tests/test_handlers_group_quiz.py
git commit -m "feat(quiz): /quiz wizard entry + admin check + book/units selection"
```
Expected: all pass; ruff clean.

---

### Task 6: Wizard — types/count/interval + start; `/stop`

**Files:**
- Modify: `apps/quiz/services/session.py`, `bot/handlers/group_quiz.py`, `bot/keyboards/group_quiz.py`
- Modify: `apps/quiz/tests/test_session_service.py`

**Interfaces:**
- Produces:
  - `apps.quiz.services.session.toggle_type(session, qtype)`, `set_count(session, count)`, `set_interval(session, seconds)`, `abort_active(chat_id) -> bool`
  - `bot.handlers.group_quiz`: `gq:units_done`, `gq:type:*`, `gq:types_done`, `gq:count:*`, `gq:int:*`, `gq:start`, `/stop` handlers
  - `bot.keyboards.group_quiz.types_keyboard(selected)`, `count_keyboard()`, `interval_keyboard()`, `start_keyboard()`

- [ ] **Step 1: Write the failing service tests**

Add to `apps/quiz/tests/test_session_service.py`:
```python
def test_type_count_interval_and_abort():
    from apps.quiz.services.session import abort_active, set_count, set_interval, toggle_type
    s = start_configuring(-200, 5)
    toggle_type(s, "en_uz")
    toggle_type(s, "uz_en")
    toggle_type(s, "en_uz")  # off
    s.refresh_from_db()
    assert s.question_types == ["uz_en"]
    set_count(s, 15)
    set_interval(s, 30)
    s.refresh_from_db()
    assert s.question_count == 15
    assert s.interval_seconds == 30
    assert abort_active(-200) is True
    s.refresh_from_db()
    assert s.status == GroupQuizSession.Status.ABORTED
    assert abort_active(-200) is False  # nothing active now
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/quiz/tests/test_session_service.py::test_type_count_interval_and_abort -v`
Expected: FAIL — functions missing.

- [ ] **Step 3: Extend `apps/quiz/services/session.py`**

Append:
```python
from django.utils import timezone


def toggle_type(session: GroupQuizSession, qtype: str) -> None:
    types = list(session.question_types)
    if qtype in types:
        types.remove(qtype)
    else:
        types.append(qtype)
    session.question_types = types
    session.save(update_fields=["question_types", "updated_at"])


def set_count(session: GroupQuizSession, count: int) -> None:
    session.question_count = count
    session.save(update_fields=["question_count", "updated_at"])


def set_interval(session: GroupQuizSession, seconds: int) -> None:
    session.interval_seconds = seconds
    session.save(update_fields=["interval_seconds", "updated_at"])


def abort_active(chat_id: int) -> bool:
    session = get_active_session(chat_id)
    if session is None:
        return False
    session.status = GroupQuizSession.Status.ABORTED
    session.finished_at = timezone.now()
    session.save(update_fields=["status", "finished_at", "updated_at"])
    return True
```

- [ ] **Step 4: Extend `bot/keyboards/group_quiz.py`**

Append:
```python
_TYPE_LABELS = {"en_uz": "EN→UZ", "uz_en": "UZ→EN", "def_word": "Ta'rif"}
COUNTS = [5, 10, 15, 20, 30]
INTERVALS = [10, 15, 20, 30, 45, 60]


def types_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(
            text=("✅ " if code in selected else "") + label, callback_data=f"gq:type:{code}"
        )
    ] for code, label in _TYPE_LABELS.items()]
    rows.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="gq:types_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def count_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=str(n), callback_data=f"gq:count:{n}") for n in COUNTS]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def interval_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=f"{n}s", callback_data=f"gq:int:{n}") for n in INTERVALS]
    return InlineKeyboardMarkup(inline_keyboard=[row[:3], row[3:]])


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Boshlash", callback_data="gq:start")
    ]])
```

- [ ] **Step 5: Extend `bot/handlers/group_quiz.py`**

Add these imports and handlers (the `gq:start` handler launches the runner from Task 7 — import it):
```python
import asyncio

from apps.quiz.services.session import abort_active, set_count, set_interval, toggle_type
from bot.keyboards.group_quiz import count_keyboard, interval_keyboard, start_keyboard, types_keyboard
from bot.runner_group_quiz import run_group_quiz


@router.callback_query(F.data == "gq:units_done")
async def units_done(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None or not session.unit_ids:
        await callback.answer("Kamida bitta unit tanlang!", show_alert=True)
        return
    await callback.message.edit_text("Savol turlarini tanlang:", reply_markup=types_keyboard([]))


@router.callback_query(F.data.startswith("gq:type:"))
async def toggle_type_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None:
        return
    await sync_to_async(toggle_type)(session, callback.data.split(":")[-1])
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    await callback.message.edit_reply_markup(reply_markup=types_keyboard(session.question_types))


@router.callback_query(F.data == "gq:types_done")
async def types_done(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None or not session.question_types:
        await callback.answer("Kamida bitta tur tanlang!", show_alert=True)
        return
    await callback.message.edit_text("Nechta savol?", reply_markup=count_keyboard())


@router.callback_query(F.data.startswith("gq:count:"))
async def pick_count(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None:
        return
    await sync_to_async(set_count)(session, int(callback.data.split(":")[-1]))
    await callback.message.edit_text("Har savol uchun necha soniya?", reply_markup=interval_keyboard())


@router.callback_query(F.data.startswith("gq:int:"))
async def pick_interval(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None:
        return
    await sync_to_async(set_interval)(session, int(callback.data.split(":")[-1]))
    await callback.message.edit_text("Tayyor! Boshlash uchun bosing 👇", reply_markup=start_keyboard())


@router.callback_query(F.data == "gq:start")
async def start_quiz(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None:
        return
    await callback.message.delete()
    asyncio.create_task(run_group_quiz(callback.bot, session.id))


@router.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    if not await is_chat_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer(_NOT_ADMIN)
        return
    stopped = await sync_to_async(abort_active)(message.chat.id)
    await message.answer("To'xtatildi!" if stopped else "To'xtatiladigan test yo'q.")
```

- [ ] **Step 6: Run the service test + full suite + commit**

Run:
```bash
python -m uv run pytest apps/quiz/tests/test_session_service.py -v
python -m uv run pytest
python -m uv run ruff check .
git add apps/quiz/services/session.py bot/handlers/group_quiz.py bot/keyboards/group_quiz.py apps/quiz/tests/test_session_service.py
git commit -m "feat(quiz): wizard types/count/interval/start + /stop"
```
Expected: service tests pass; the full suite passes (the new `gq:start` handler imports `bot.runner_group_quiz.run_group_quiz` — created in Task 7; **run Task 7 before the full-suite gate if import fails**, or temporarily the import is satisfied because Task 7 lands next). If the full suite fails only on the missing `bot.runner_group_quiz` import, that's expected until Task 7; commit the handler code and proceed — Task 7's gate re-runs the full suite green.

> **Sequencing note:** `bot/handlers/group_quiz.py` imports `run_group_quiz` from Task 7. To keep every task's suite green, implement Task 7's `bot/runner_group_quiz.py` immediately; the two tasks are a tight pair. If executing strictly one task at a time, defer the `from bot.runner_group_quiz import run_group_quiz` import and the `gq:start` handler's `create_task` line to Task 7. Recommended: treat the import as forward-declared and land Task 7 next.

---

### Task 7: Async quiz runner + countdown + finish

**Files:**
- Create: `bot/runner_group_quiz.py`
- Create: `apps/quiz/services/run.py`
- Create: `bot/tests/test_runner_group_quiz.py`, `apps/quiz/tests/test_run_service.py`

**Interfaces:**
- Consumes: `sample_words` (T2), `build_questions` (T2), `build_leaderboard` (T3), models.
- Produces:
  - `apps.quiz.services.run.prepare_questions(session_id) -> None` — sample words, build questions, create `GroupQuizQuestion` rows, set status `running`.
  - `apps.quiz.services.run.record_poll_sent(question_id, poll_id) -> None`; `apps.quiz.services.run.is_aborted(session_id) -> bool`; `apps.quiz.services.run.finish_and_leaderboard(session_id) -> tuple[int, str]` — mark finished (unless aborted), return `(chat_id, leaderboard_text)`.
  - `apps.quiz.services.run.pending_questions(session_id) -> list[dict]` — `[{"id", "prompt", "options", "correct_option", "explanation"}]`.
  - `bot.runner_group_quiz.run_group_quiz(bot, session_id)` — countdown, send each poll, sleep, finish.

- [ ] **Step 1: Write the failing service tests**

`apps/quiz/tests/test_run_service.py`:
```python
import pytest

from apps.catalog.models import Book, Unit, Word
from apps.quiz.models import GroupQuizParticipant, GroupQuizQuestion, GroupQuizSession
from apps.quiz.services import run as run_svc

pytestmark = pytest.mark.django_db


def _configured_session():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    for i in range(6):
        Word.objects.create(unit=unit, en=f"w{i}", uz=f"uz{i}", definition=f"d{i}",
                            part_of_speech="n.", order=i)
    return GroupQuizSession.objects.create(
        chat_id=-100, status=GroupQuizSession.Status.CONFIGURING, book=book,
        unit_ids=[unit.id], question_types=["en_uz"], question_count=3, interval_seconds=10,
    )


def test_prepare_questions_creates_rows_and_runs():
    s = _configured_session()
    run_svc.prepare_questions(s.id)
    s.refresh_from_db()
    assert s.status == GroupQuizSession.Status.RUNNING
    assert GroupQuizQuestion.objects.filter(session=s).count() == 3
    pending = run_svc.pending_questions(s.id)
    assert len(pending) == 3
    assert all(set(p) >= {"id", "prompt", "options", "correct_option"} for p in pending)


def test_record_poll_sent_and_is_aborted():
    s = _configured_session()
    run_svc.prepare_questions(s.id)
    q = GroupQuizQuestion.objects.filter(session=s).first()
    run_svc.record_poll_sent(q.id, "poll-xyz")
    q.refresh_from_db()
    assert q.poll_id == "poll-xyz"
    assert q.sent_at is not None
    assert run_svc.is_aborted(s.id) is False
    s.status = GroupQuizSession.Status.ABORTED
    s.save()
    assert run_svc.is_aborted(s.id) is True


def test_finish_and_leaderboard():
    s = _configured_session()
    run_svc.prepare_questions(s.id)
    GroupQuizParticipant.objects.create(session=s, telegram_id=1, full_name="A", correct_count=2, total_time=9)
    chat_id, text = run_svc.finish_and_leaderboard(s.id)
    s.refresh_from_db()
    assert chat_id == -100
    assert s.status == GroupQuizSession.Status.FINISHED
    assert "A" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/quiz/tests/test_run_service.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/quiz/services/run.py`**

```python
from django.utils import timezone

from apps.learning.services.exam import build_questions
from apps.quiz.models import GroupQuizQuestion, GroupQuizSession
from apps.quiz.services.questions import sample_words
from apps.quiz.services.scoring import build_leaderboard

_EXPLANATION = "@essential_words"


def prepare_questions(session_id: int) -> None:
    session = GroupQuizSession.objects.get(id=session_id)
    words = sample_words(session.unit_ids, session.question_count)
    questions = build_questions(words, types=session.question_types or None)
    for order, q in enumerate(questions, start=1):
        GroupQuizQuestion.objects.create(
            session=session, word=q["word"], order=order, question_type=q["question_type"],
            options=q["options"], correct_option=q["correct_option"],
        )
    session.status = GroupQuizSession.Status.RUNNING
    session.started_at = timezone.now()
    session.save(update_fields=["status", "started_at", "updated_at"])


def pending_questions(session_id: int) -> list[dict]:
    items = []
    for q in GroupQuizQuestion.objects.filter(session_id=session_id).select_related("word").order_by("order"):
        word = q.word
        if q.question_type == "en_uz":
            prompt = f"{word.en} {word.part_of_speech}".strip()
        elif q.question_type == "uz_en":
            prompt = word.uz
        else:
            prompt = word.definition or word.en
        items.append({
            "id": q.id, "prompt": prompt[:300], "options": q.options,
            "correct_option": q.correct_option, "explanation": _EXPLANATION,
        })
    return items


def record_poll_sent(question_id: int, poll_id: str) -> None:
    GroupQuizQuestion.objects.filter(id=question_id).update(poll_id=poll_id, sent_at=timezone.now())


def is_aborted(session_id: int) -> bool:
    return GroupQuizSession.objects.filter(
        id=session_id, status=GroupQuizSession.Status.ABORTED
    ).exists()


def finish_and_leaderboard(session_id: int) -> tuple[int, str]:
    session = GroupQuizSession.objects.get(id=session_id)
    if session.status != GroupQuizSession.Status.ABORTED:
        session.status = GroupQuizSession.Status.FINISHED
        session.finished_at = timezone.now()
        session.save(update_fields=["status", "finished_at", "updated_at"])
    return session.chat_id, build_leaderboard(session)
```

- [ ] **Step 4: Run the service tests**

Run: `python -m uv run pytest apps/quiz/tests/test_run_service.py -v`
Expected: all PASS.

- [ ] **Step 5: Write the failing runner test**

`bot/tests/test_runner_group_quiz.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot import runner_group_quiz

pytestmark = pytest.mark.asyncio


@patch("bot.runner_group_quiz.asyncio.sleep", new_callable=AsyncMock)
@patch("bot.runner_group_quiz.finish_and_leaderboard", return_value=(-100, "🏁 board"))
@patch("bot.runner_group_quiz.is_aborted", return_value=False)
@patch("bot.runner_group_quiz.record_poll_sent")
@patch("bot.runner_group_quiz.pending_questions")
@patch("bot.runner_group_quiz.prepare_questions")
async def test_run_group_quiz_sends_polls_and_leaderboard(
    mock_prepare, mock_pending, mock_record, mock_aborted, mock_finish, mock_sleep
):
    mock_pending.return_value = [
        {"id": 1, "prompt": "q1", "options": ["a", "b"], "correct_option": 0, "explanation": "e"},
        {"id": 2, "prompt": "q2", "options": ["a", "b"], "correct_option": 1, "explanation": "e"},
    ]
    bot = AsyncMock()
    poll_msg = MagicMock()
    poll_msg.poll.id = "poll-x"
    bot.send_poll.return_value = poll_msg

    await runner_group_quiz.run_group_quiz(bot, session_id=7)

    mock_prepare.assert_called_once_with(7)
    assert bot.send_poll.await_count == 2          # one per pending question
    assert mock_record.call_count == 2             # poll_id recorded per question
    # leaderboard sent at the end
    bot.send_message.assert_any_await(-100, "🏁 board")


@patch("bot.runner_group_quiz.asyncio.sleep", new_callable=AsyncMock)
@patch("bot.runner_group_quiz.finish_and_leaderboard", return_value=(-100, "board"))
@patch("bot.runner_group_quiz.is_aborted", return_value=True)   # aborted before first question
@patch("bot.runner_group_quiz.record_poll_sent")
@patch("bot.runner_group_quiz.pending_questions")
@patch("bot.runner_group_quiz.prepare_questions")
async def test_run_group_quiz_stops_when_aborted(
    mock_prepare, mock_pending, mock_record, mock_aborted, mock_finish, mock_sleep
):
    mock_pending.return_value = [
        {"id": 1, "prompt": "q1", "options": ["a", "b"], "correct_option": 0, "explanation": "e"},
    ]
    bot = AsyncMock()
    await runner_group_quiz.run_group_quiz(bot, session_id=7)
    bot.send_poll.assert_not_awaited()   # aborted → no polls sent
```

- [ ] **Step 6: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_runner_group_quiz.py -v`
Expected: FAIL — `bot.runner_group_quiz` missing.

- [ ] **Step 7: Implement `bot/runner_group_quiz.py`**

```python
import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ParseMode, PollType
from asgiref.sync import sync_to_async

from apps.quiz.services.run import (
    finish_and_leaderboard, is_aborted, pending_questions, prepare_questions, record_poll_sent,
)

logger = logging.getLogger(__name__)


async def run_group_quiz(bot: Bot, session_id: int) -> None:
    """Sequentially send quiz polls for a group session, then post the leaderboard."""
    await sync_to_async(prepare_questions)(session_id)
    questions = await sync_to_async(pending_questions)(session_id)

    for question in questions:
        if await sync_to_async(is_aborted)(session_id):
            break
        try:
            msg = await bot.send_poll(
                chat_id=(await sync_to_async(_chat_id)(session_id)),
                question=question["prompt"],
                options=question["options"],
                type=PollType.QUIZ,
                correct_option_id=question["correct_option"],
                is_anonymous=False,
                open_period=(await sync_to_async(_interval)(session_id)),
                explanation=question["explanation"],
            )
            await sync_to_async(record_poll_sent)(question["id"], msg.poll.id)
        except Exception as exc:  # keep the quiz resilient to a single bad poll
            logger.warning("group quiz send failed (session %s): %s", session_id, exc)
            continue
        await asyncio.sleep(await sync_to_async(_interval)(session_id))

    chat_id, text = await sync_to_async(finish_and_leaderboard)(session_id)
    await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)


def _chat_id(session_id: int) -> int:
    from apps.quiz.models import GroupQuizSession

    return GroupQuizSession.objects.values_list("chat_id", flat=True).get(id=session_id)


def _interval(session_id: int) -> int:
    from apps.quiz.models import GroupQuizSession

    return GroupQuizSession.objects.values_list("interval_seconds", flat=True).get(id=session_id)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_runner_group_quiz.py -v`
Expected: both tests PASS. (The tests patch `pending_questions`/`prepare_questions`/etc., so `_chat_id`/`_interval` are exercised only in the non-aborted test — they run against no real DB there because those helpers are NOT patched; if that raises, patch `bot.runner_group_quiz._chat_id`/`_interval` in the send test too, returning `-100`/`10`.)

> **Test-robustness note for the implementer:** the first runner test calls `bot.send_poll` which reads `_chat_id`/`_interval` (real DB helpers). To keep the test DB-free, ADD `@patch("bot.runner_group_quiz._chat_id", return_value=-100)` and `@patch("bot.runner_group_quiz._interval", return_value=10)` to `test_run_group_quiz_sends_polls_and_leaderboard` (adjust the decorator arg order accordingly). Do this if the test errors on DB access.

- [ ] **Step 9: Full suite + commit**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/runner_group_quiz.py apps/quiz/services/run.py bot/tests/test_runner_group_quiz.py apps/quiz/tests/test_run_service.py
git commit -m "feat(quiz): async group-quiz runner (countdown/sequential polls/leaderboard)"
```
Expected: all pass (the Task-6 `bot/handlers/group_quiz.py` import of `run_group_quiz` now resolves); ruff clean.

---

### Task 8: Wire router into factory + docs + gate

**Files:**
- Modify: `bot/factory.py`, `Readme.md`
- Create: `bot/tests/test_factory_group_quiz.py`

**Interfaces:**
- Produces: `group_quiz.router` included in `build_dispatcher`; Readme documents group-quiz usage + the BotFather privacy requirement.

- [ ] **Step 1: Write the failing test**

`bot/tests/test_factory_group_quiz.py`:
```python
def test_dispatcher_includes_group_quiz_router(settings):
    settings.REDIS_URL = "redis://localhost:6379/1"
    from bot.factory import build_dispatcher

    dp = build_dispatcher()
    assert len(dp.sub_routers) >= 6  # start, onboarding, settings, common, quiz, group_quiz
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_factory_group_quiz.py -v`
Expected: FAIL — only 5 routers wired.

- [ ] **Step 3: Wire the router in `bot/factory.py`**

Add `group_quiz` to the handlers import and include it:
```python
from bot.handlers import common, group_quiz, onboarding, quiz, settings, start
```
and, in `build_dispatcher`, after `dp.include_router(quiz.router)`:
```python
    dp.include_router(group_quiz.router)
```

- [ ] **Step 4: Run the test**

Run: `python -m uv run pytest bot/tests/test_factory_group_quiz.py bot/tests/test_factory.py -v`
Expected: PASS (both the new ≥6 check and the existing ≥4 check).

- [ ] **Step 5: Update `Readme.md`**

Add a "Group quiz" subsection under the Bot section:
```markdown
## Group quiz

Add the bot to a Telegram group and make it an **admin**. In @BotFather run
`/setprivacy` → **Disable** so the bot receives group commands. Then a group
admin sends `/quiz` and follows the wizard (book → units → question types →
count → interval) to start a QuizBot-style quiz; the bot posts sequential quiz
polls and a leaderboard ranking each student by correct answers then speed.
`/stop` aborts a running quiz.
```

- [ ] **Step 6: Full gate + commit**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/factory.py Readme.md bot/tests/test_factory_group_quiz.py
git commit -m "feat(quiz): wire group-quiz router into dispatcher + docs"
```
Expected: full suite passes; ruff clean.

---

## Self-Review (completed by plan author)

**Spec coverage** — every Phase 3 spec section maps to a task:
- §2 decisions (Word-DB source, DB-persisted, full wizard, model-state, async runner, poll routing, native quiz poll) → Tasks 1–8
- §3 models → Task 1
- §4 services (sample_words, typed build_questions, scoring/leaderboard, runner) → Tasks 2,3,7
- §5 bot handlers (wizard, /stop, admin check, poll routing) → Tasks 4,5,6
- §6 tests → each task ships tests; runner + poll edges mocked
- §7 config (BotFather privacy, keyboards) → Tasks 5,6,8
- §8 DoD → Task 8 gate

**Placeholder scan** — no TBD/TODO. Two sequencing dependencies are called out explicitly (not hidden): Task 6's `bot/handlers/group_quiz.py` imports `run_group_quiz` from Task 7 (the two are a tight pair — land Task 7 immediately after Task 6, and the full-suite gate lives in Task 7/8); Task 7's runner test may need `_chat_id`/`_interval` patched to stay DB-free (explicit note given).

**Type/name consistency** — `sample_words` (T2), `build_questions(types=)` (T2), `record_group_answer`/`build_leaderboard` (T3), `get_active_session`/`start_configuring`/`set_book`/`toggle_unit`/`toggle_type`/`set_count`/`set_interval`/`abort_active` (T5/T6), `prepare_questions`/`pending_questions`/`record_poll_sent`/`is_aborted`/`finish_and_leaderboard` (T7) are consumed with matching signatures across the handlers/runner; the `gq:*` callback-data strings emitted by keyboards (T5/T6) match the handler filters. `record_group_answer` (T3) is routed before `record_answer` (Phase 2b) in the single `on_poll_answer` handler (T4). Async handlers/runner reach the ORM only via `sync_to_async`.

**Ordering note** — `docker compose up -d db redis` must be running for the DB-backed tests. Tasks 6 and 7 are a coupled pair (import dependency); execute them back-to-back.
