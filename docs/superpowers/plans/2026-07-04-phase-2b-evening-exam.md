# Faza 2b — Kechki imtihon + SRS (Evening Exam) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** At each user's exam time, send native Telegram quiz polls over the day's words (+ SRS-due reviews), grade answers via a bot poll-answer handler, update each word's SM-2 schedule, and send a daily report when the exam window closes.

**Architecture:** A Celery Beat task (`dispatch_evening_exams`) enqueues a per-user `run_exam` that generates questions (3 types + distractors), sends quiz polls (sync aiogram wrapper returning `poll_id`), and stores `ExamQuestion` rows keyed by `poll_id`. The running aiogram bot's `poll_answer` handler looks each poll up by `poll_id`, records the answer, applies SM-2, and increments the session score. A second Beat task (`finalize_due_exams`) closes sessions past the window and sends the report. All DB/logic is sync; only the aiogram poll sender + poll-answer handler are async edges.

**Tech Stack:** Django 6 ORM (sync) · Celery + django-celery-beat · aiogram 3.x quiz polls + poll_answer · SM-2 · pytest + pytest-django + pytest-asyncio.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-04-phase-2b-evening-exam-design.md`. Phases 0/1/2a are complete on `main`.
- Run via uv (not on PATH): `python -m uv run pytest`, `python -m uv run python manage.py ...`.
- Postgres + Redis via `docker compose up -d db redis` for DB tests.
- New model `apps.learning.models.ExamQuestion` (spec §3). SM-2 UPDATES the existing `WordProgress` (Phase 2a). `DailySession.status` uses `exam_sent`/`completed`; `score`/`total`/`exam_sent_at`/`completed_at` are filled here.
- Sync services; async only at the aiogram poll sender (`send_quiz_poll`) and the `poll_answer` handler (which bridges to a sync `record_answer` via `sync_to_async`).
- Question types round-robin per batch: `en_uz`, `uz_en`, `def_word` (0=Mon..6=Sun unaffected). Distractors: 3 distinct, from the same book when possible, else global fallback.
- Telegram limits: poll question ≤ 300 chars, each option ≤ 100 chars — truncate in `build_questions`.
- Idempotent: `run_exam` only fires for a session in `delivered` status (→ `exam_sent`); `record_answer` skips an already-answered question.
- Settings: `EXAM_WINDOW_MINUTES` (default 60), `EXAM_REVIEW_CAP` (default 10).
- Two new Beat tasks registered by the existing `setup_periodic_tasks` command.
- OUT of scope: group quiz (Phase 3), nudges/roles (Phase 4), web (Phase 5).
- TDD; pristine output. Commit footer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

### Prerequisite (once, before Task 1)

```bash
git checkout main && git checkout -b phase-2b-evening-exam
```

---

### Task 1: ExamQuestion model + admin + settings

**Files:**
- Modify: `apps/learning/models.py`, `apps/learning/admin.py`, `config/settings/base.py`
- Create: `apps/learning/tests/test_exam_models.py`
- Create (generated): `apps/learning/migrations/0003_*.py`

**Interfaces:**
- Produces: `apps.learning.models.ExamQuestion` (daily_session, word, question_type, poll_id unique, options, correct_option, chosen_option, is_correct, answered_at; `QType` TextChoices en_uz/uz_en/def_word); settings `EXAM_WINDOW_MINUTES`, `EXAM_REVIEW_CAP`.

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_exam_models.py`:
```python
import pytest
from django.db import IntegrityError

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, ExamQuestion

pytestmark = pytest.mark.django_db


def _session_and_word():
    user = User.objects.create(first_name="T")
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    session = DailySession.objects.create(user=user, date="2026-07-04")
    return session, word


def test_exam_question_defaults_and_poll_id_unique():
    session, word = _session_and_word()
    q = ExamQuestion.objects.create(
        daily_session=session, word=word, question_type=ExamQuestion.QType.EN_UZ,
        poll_id="poll-1", options=["a", "b", "c", "d"], correct_option=0,
    )
    assert q.chosen_option is None
    assert q.is_correct is None
    assert list(session.questions.all()) == [q]
    with pytest.raises(IntegrityError):
        ExamQuestion.objects.create(
            daily_session=session, word=word, question_type=ExamQuestion.QType.UZ_EN,
            poll_id="poll-1", options=["a"], correct_option=0,
        )


def test_exam_settings_present(settings):
    assert isinstance(settings.EXAM_WINDOW_MINUTES, int)
    assert isinstance(settings.EXAM_REVIEW_CAP, int)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_exam_models.py -v`
Expected: FAIL — `ExamQuestion` / settings missing.

- [ ] **Step 3: Add the model to `apps/learning/models.py`**

Append (keep existing models):
```python
class ExamQuestion(TimeStampedModel):
    class QType(models.TextChoices):
        EN_UZ = "en_uz", "EN→UZ"
        UZ_EN = "uz_en", "UZ→EN"
        DEF_WORD = "def_word", "Definition"

    daily_session = models.ForeignKey(
        DailySession, on_delete=models.CASCADE, related_name="questions"
    )
    word = models.ForeignKey("catalog.Word", on_delete=models.CASCADE)
    question_type = models.CharField(max_length=10, choices=QType.choices)
    poll_id = models.CharField(max_length=64, unique=True, db_index=True)
    options = models.JSONField(default=list)
    correct_option = models.PositiveSmallIntegerField()
    chosen_option = models.PositiveSmallIntegerField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return f"ExamQuestion(session={self.daily_session_id}, word={self.word_id})"
```

- [ ] **Step 4: Add settings**

In `config/settings/base.py`, near the other app settings, add:
```python
EXAM_WINDOW_MINUTES = env.int("EXAM_WINDOW_MINUTES", default=60)
EXAM_REVIEW_CAP = env.int("EXAM_REVIEW_CAP", default=10)
```

- [ ] **Step 5: Make migrations and run tests**

Run:
```bash
python -m uv run python manage.py makemigrations learning
python -m uv run pytest apps/learning/tests/test_exam_models.py -v
```
Expected: migration `0003_*` created; 2 tests PASS.

- [ ] **Step 6: Add admin**

In `apps/learning/admin.py`, add:
```python
from .models import DailySession, ExamQuestion, LearningProfile, WordProgress


@admin.register(ExamQuestion)
class ExamQuestionAdmin(ModelAdmin):
    list_display = ("daily_session", "word", "question_type", "is_correct", "answered_at")
    list_filter = ("question_type", "is_correct")
    raw_id_fields = ("daily_session", "word")
    search_fields = ("poll_id", "word__en")
```
(Merge the import line with the existing `from .models import ...`.)

- [ ] **Step 7: Migrate, full suite, ruff, commit**

Run:
```bash
python -m uv run python manage.py migrate
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning config/settings/base.py
git commit -m "feat(learning): ExamQuestion model + admin + exam settings"
```
Expected: migrate clean; full suite passes (97 prior + 2 new = 99); ruff clean.

---

### Task 2: SM-2 scheduling service

**Files:**
- Create: `apps/learning/services/srs.py`
- Create: `apps/learning/tests/test_srs.py`

**Interfaces:**
- Consumes: `apps.learning.models.WordProgress`.
- Produces:
  - `apps.learning.services.srs.apply_sm2(progress, correct: bool) -> None` — mutates + saves the WordProgress per SM-2.
  - `apps.learning.services.srs.grade_answer(user, word, correct: bool) -> WordProgress` — get_or_create then apply_sm2.

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_srs.py`:
```python
import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import WordProgress
from apps.learning.services.srs import apply_sm2, grade_answer

pytestmark = pytest.mark.django_db


def _progress():
    user = User.objects.create(first_name="T")
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    return WordProgress.objects.create(user=user, word=word), user, word


def test_first_correct_sets_interval_1_learning():
    p, _, _ = _progress()
    apply_sm2(p, correct=True)
    assert p.repetitions == 1
    assert p.interval_days == 1
    assert p.status == WordProgress.Status.LEARNING
    assert p.correct_count == 1
    assert p.next_review == timezone.now().date() + datetime.timedelta(days=1)


def test_third_correct_marks_known_and_grows_interval():
    p, _, _ = _progress()
    apply_sm2(p, correct=True)   # rep1, interval 1
    apply_sm2(p, correct=True)   # rep2, interval 6
    apply_sm2(p, correct=True)   # rep3, interval round(6*ease)
    assert p.repetitions == 3
    assert p.status == WordProgress.Status.KNOWN
    assert p.interval_days > 6


def test_wrong_resets_repetitions_and_lowers_ease():
    p, _, _ = _progress()
    apply_sm2(p, correct=True)
    apply_sm2(p, correct=True)
    ease_before = p.ease_factor
    apply_sm2(p, correct=False)
    assert p.repetitions == 0
    assert p.interval_days == 1
    assert p.ease_factor == pytest.approx(max(1.3, ease_before - 0.2))
    assert p.wrong_count == 1


def test_ease_never_below_min():
    p, _, _ = _progress()
    for _ in range(10):
        apply_sm2(p, correct=False)
    assert p.ease_factor >= 1.3


def test_grade_answer_creates_progress():
    _, user, word = _progress()
    word2 = Word.objects.create(unit=word.unit, en="agree", uz="b", order=2)
    p = grade_answer(user, word2, correct=True)
    assert p.repetitions == 1
    assert WordProgress.objects.filter(user=user, word=word2).exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_srs.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/learning/services/srs.py`**

```python
import datetime

from django.utils import timezone

from apps.learning.models import WordProgress

MIN_EASE = 1.3


def apply_sm2(progress: WordProgress, correct: bool) -> None:
    """Update a WordProgress in place using the SM-2 algorithm, then save."""
    if correct:
        progress.repetitions += 1
        if progress.repetitions == 1:
            progress.interval_days = 1
        elif progress.repetitions == 2:
            progress.interval_days = 6
        else:
            progress.interval_days = round(progress.interval_days * progress.ease_factor)
        progress.ease_factor = progress.ease_factor + 0.1
        progress.correct_count += 1
    else:
        progress.repetitions = 0
        progress.interval_days = 1
        progress.ease_factor = max(MIN_EASE, progress.ease_factor - 0.2)
        progress.wrong_count += 1

    today = timezone.now().date()
    progress.next_review = today + datetime.timedelta(days=progress.interval_days)
    progress.status = (
        WordProgress.Status.KNOWN if progress.repetitions >= 3 else WordProgress.Status.LEARNING
    )
    progress.last_reviewed = timezone.now()
    progress.save()


def grade_answer(user, word, correct: bool) -> WordProgress:
    progress, _ = WordProgress.objects.get_or_create(user=user, word=word)
    apply_sm2(progress, correct)
    return progress
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_srs.py -v`
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/learning/services/srs.py apps/learning/tests/test_srs.py
git commit -m "feat(learning): SM-2 apply_sm2 + grade_answer"
```

---

### Task 3: Question generation + exam word selection

**Files:**
- Create: `apps/learning/services/exam.py`
- Create: `apps/learning/tests/test_exam_questions.py`

**Interfaces:**
- Consumes: `Word`, `DailySession`, `WordProgress`, `ExamQuestion.QType`.
- Produces:
  - `apps.learning.services.exam.select_exam_words(session, review_cap) -> list[Word]` — the session's words + up to `review_cap` SRS-due review words (WordProgress `next_review <= today`, status != new), deduped, day-words first.
  - `apps.learning.services.exam.build_questions(words) -> list[dict]` — one question per word, type round-robin (`en_uz`/`uz_en`/`def_word`); each dict = `{"word": Word, "question_type": str, "prompt": str, "options": list[str], "correct_option": int, "explanation": str}`. Prompt ≤ 300 chars, each option ≤ 100 chars; 4 distinct options.

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_exam_questions.py`:
```python
import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, SessionWord, WordProgress
from apps.learning.services.exam import build_questions, select_exam_words

pytestmark = pytest.mark.django_db


@pytest.fixture
def book_words():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    words = [
        Word.objects.create(unit=unit, en=f"w{i}", uz=f"uz{i}", definition=f"def {i}",
                            part_of_speech="n.", order=i)
        for i in range(1, 7)
    ]
    return book, unit, words


def test_build_questions_round_robin_types(book_words):
    _, _, words = book_words
    qs = build_questions(words[:3])
    assert [q["question_type"] for q in qs] == ["en_uz", "uz_en", "def_word"]


def test_build_questions_options_have_correct_and_are_distinct(book_words):
    _, _, words = book_words
    qs = build_questions(words[:4])
    for q in qs:
        assert len(q["options"]) == 4
        assert len(set(q["options"])) == 4  # distinct
        assert q["options"][q["correct_option"]] is not None
        # correct value is at the correct_option index
        assert 0 <= q["correct_option"] < 4


def test_en_uz_correct_option_is_the_uz_translation(book_words):
    _, _, words = book_words
    q = build_questions([words[0]])[0]  # index 0 → en_uz
    assert q["question_type"] == "en_uz"
    assert q["options"][q["correct_option"]] == words[0].uz


def test_select_exam_words_includes_day_and_due_reviews(book_words):
    _, unit, words = book_words
    user = User.objects.create(first_name="T")
    session = DailySession.objects.create(user=user, date=timezone.now().date())
    # day words: w1, w2
    for i, w in enumerate(words[:2], start=1):
        SessionWord.objects.create(daily_session=session, word=w, order=i)
    # a due review word: w5 (learning, next_review yesterday)
    WordProgress.objects.create(
        user=user, word=words[4], status=WordProgress.Status.LEARNING,
        next_review=timezone.now().date() - datetime.timedelta(days=1),
    )
    # a not-due word: w6 (next_review tomorrow) — excluded
    WordProgress.objects.create(
        user=user, word=words[5], status=WordProgress.Status.LEARNING,
        next_review=timezone.now().date() + datetime.timedelta(days=1),
    )
    result = select_exam_words(session, review_cap=10)
    ens = [w.en for w in result]
    assert "w1" in ens and "w2" in ens   # day words
    assert "w5" in ens                    # due review
    assert "w6" not in ens                # not due
    assert len(ens) == len(set(ens))      # deduped
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_exam_questions.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/learning/services/exam.py`**

```python
import random

from django.utils import timezone

from apps.catalog.models import Word
from apps.learning.models import DailySession, ExamQuestion, WordProgress

_TYPES = [ExamQuestion.QType.EN_UZ, ExamQuestion.QType.UZ_EN, ExamQuestion.QType.DEF_WORD]
_EXPLANATION = "@essential_words"


def select_exam_words(session: DailySession, review_cap: int) -> list[Word]:
    """The session's words plus up to review_cap SRS-due review words, deduped."""
    day_words = list(session.words.all())
    seen = {w.pk for w in day_words}
    today = timezone.now().date()
    due = (
        Word.objects.filter(progress__user=session.user, progress__next_review__lte=today)
        .exclude(progress__status=WordProgress.Status.NEW)
        .exclude(pk__in=seen)
        .distinct()
        .order_by("progress__next_review")[:review_cap]
    )
    return day_words + list(due)


def _distractors(word: Word, field: str, count: int) -> list[str]:
    """`count` distinct values of `field` from other words (same book first, else global)."""
    correct_value = getattr(word, field)

    def _pool(qs):
        return [
            v for v in qs.exclude(pk=word.pk).values_list(field, flat=True)
            if v and v != correct_value
        ]

    pool = list(dict.fromkeys(_pool(Word.objects.filter(unit__book=word.unit.book))))
    if len(pool) < count:
        extra = _pool(Word.objects.all())
        for v in dict.fromkeys(extra):
            if v not in pool:
                pool.append(v)
    random.shuffle(pool)
    return pool[:count]


def _question_for(word: Word, qtype: str) -> dict:
    if qtype == ExamQuestion.QType.EN_UZ:
        prompt = f"{word.en} {word.part_of_speech}".strip()
        correct = word.uz
        options = [correct, *_distractors(word, "uz", 3)]
    elif qtype == ExamQuestion.QType.UZ_EN:
        prompt = word.uz
        correct = word.en
        options = [correct, *_distractors(word, "en", 3)]
    else:  # DEF_WORD
        prompt = word.definition or word.en
        correct = word.en
        options = [correct, *_distractors(word, "en", 3)]

    random.shuffle(options)
    options = [o[:100] for o in options]
    correct_option = options.index(correct[:100])
    return {
        "word": word,
        "question_type": qtype,
        "prompt": prompt[:300],
        "options": options,
        "correct_option": correct_option,
        "explanation": _EXPLANATION,
    }


def build_questions(words: list[Word]) -> list[dict]:
    return [_question_for(word, _TYPES[i % 3]) for i, word in enumerate(words)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_exam_questions.py -v`
Expected: all PASS. (The `book_words` fixture has 6 words, enough for 3 distinct distractors.)

- [ ] **Step 5: Commit**

```bash
git add apps/learning/services/exam.py apps/learning/tests/test_exam_questions.py
git commit -m "feat(learning): exam question generation + SRS-due word selection"
```

---

### Task 4: Exam due-check + quiz-poll sender

**Files:**
- Modify: `apps/learning/services/scheduling.py`, `bot/sender.py`
- Create: `apps/learning/tests/test_exam_scheduling.py`, `bot/tests/test_sender_poll.py`

**Interfaces:**
- Produces:
  - `apps.learning.services.scheduling.is_due_for_exam(profile, now_utc) -> bool` — like `is_due_for_delivery` but matches `exam_time`.
  - `bot.sender.send_quiz_poll(chat_id, question, options, correct_option, explanation=None) -> str` — sends a native quiz poll and returns its `poll_id`; `bot.sender._send_quiz_poll(bot, ...)` async worker.

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_exam_scheduling.py`:
```python
import datetime
from unittest.mock import MagicMock

from apps.learning.services.scheduling import is_due_for_exam


def _profile(**kw):
    p = MagicMock()
    p.is_active = kw.get("is_active", True)
    p.onboarded = kw.get("onboarded", True)
    p.timezone = kw.get("timezone", "Asia/Tashkent")
    p.study_weekdays = kw.get("study_weekdays", [0, 1, 2, 3, 4, 5, 6])
    p.exam_time = kw.get("exam_time", datetime.time(20, 0))
    return p


def _utc(hh, mm):
    return datetime.datetime(2026, 7, 6, hh, mm, tzinfo=datetime.UTC)


def test_due_for_exam_when_local_matches():
    # 15:00 UTC = 20:00 Asia/Tashkent (UTC+5), 2026-07-06 Monday
    assert is_due_for_exam(_profile(), _utc(15, 0)) is True


def test_not_due_for_exam_off_minute():
    assert is_due_for_exam(_profile(), _utc(15, 1)) is False
```

`bot/tests/test_sender_poll.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot import sender

pytestmark = pytest.mark.asyncio


async def test_send_quiz_poll_returns_poll_id_and_sets_quiz_type():
    bot = AsyncMock()
    msg = MagicMock()
    msg.poll.id = "poll-xyz"
    bot.send_poll.return_value = msg

    poll_id = await sender._send_quiz_poll(
        bot, 555, "Question?", ["a", "b", "c", "d"], 2, explanation="expl"
    )
    assert poll_id == "poll-xyz"
    kwargs = bot.send_poll.call_args.kwargs
    assert kwargs["correct_option_id"] == 2
    assert kwargs["is_anonymous"] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_exam_scheduling.py bot/tests/test_sender_poll.py -v`
Expected: FAIL — `is_due_for_exam` / `_send_quiz_poll` missing.

- [ ] **Step 3: Add `is_due_for_exam`**

Append to `apps/learning/services/scheduling.py`:
```python
def is_due_for_exam(profile, now_utc):
    """True if this profile should receive its evening exam at `now_utc`."""
    if not profile.is_active or not profile.onboarded:
        return False
    local = now_utc.astimezone(ZoneInfo(profile.timezone))
    if local.weekday() not in profile.study_weekdays:
        return False
    return local.hour == profile.exam_time.hour and local.minute == profile.exam_time.minute
```
(`ZoneInfo` is already imported in this module from Phase 2a.)

- [ ] **Step 4: Add `send_quiz_poll` to `bot/sender.py`**

Add these imports at the top if missing and the functions at the end:
```python
from aiogram.enums import ParseMode, PollType
```
(`ParseMode` is already imported; add `PollType` to the same line.)

```python
async def _send_quiz_poll(
    bot: Bot, chat_id: int, question: str, options: list[str],
    correct_option: int, explanation: str | None = None,
) -> str:
    msg = await bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=options,
        type=PollType.QUIZ,
        correct_option_id=correct_option,
        is_anonymous=False,
        explanation=explanation,
    )
    return msg.poll.id


def send_quiz_poll(
    chat_id: int, question: str, options: list[str],
    correct_option: int, explanation: str | None = None,
) -> str:
    async def _run() -> str:
        bot = _make_bot()
        try:
            return await _send_quiz_poll(bot, chat_id, question, options, correct_option, explanation)
        finally:
            await bot.session.close()

    return asyncio.run(_run())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_exam_scheduling.py bot/tests/test_sender_poll.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/learning/services/scheduling.py bot/sender.py apps/learning/tests/test_exam_scheduling.py bot/tests/test_sender_poll.py
git commit -m "feat: is_due_for_exam + send_quiz_poll (native quiz poll)"
```

---

### Task 5: Exam orchestration + dispatch task

**Files:**
- Create: `apps/learning/services/exam_deliver.py`
- Modify: `apps/learning/tasks.py`
- Create: `apps/learning/tests/test_run_exam.py`, `apps/learning/tests/test_exam_tasks.py`

**Interfaces:**
- Consumes: `select_exam_words`/`build_questions` (T3), `send_quiz_poll` (T4), `is_due_for_exam` (T4), models (T1), `EXAM_REVIEW_CAP`.
- Produces:
  - `apps.learning.services.exam_deliver.run_exam(user_id) -> DailySession | None` — finds today's `delivered` session, generates + sends quiz polls, stores `ExamQuestion` rows, marks `exam_sent` with `total`/`score=0`. None if no delivered session / no words / blocked.
  - `apps.learning.tasks.send_exam(user_id)` (shared_task wrapping run_exam), `apps.learning.tasks.dispatch_evening_exams()` (shared_task).

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_run_exam.py`:
```python
import datetime
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, ExamQuestion, LearningProfile, SessionWord
from apps.learning.services import exam_deliver

pytestmark = pytest.mark.django_db


@pytest.fixture
def delivered_session():
    user = User.objects.create(first_name="T")
    TelegramAccount.objects.create(user=user, telegram_id=555)
    LearningProfile.objects.create(user=user, onboarded=True)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    words = [Word.objects.create(unit=unit, en=f"w{i}", uz=f"uz{i}", definition=f"d{i}",
                                 part_of_speech="n.", order=i) for i in range(1, 7)]
    session = DailySession.objects.create(
        user=user, date=timezone.now().date(), status=DailySession.Status.DELIVERED
    )
    for i, w in enumerate(words[:3], start=1):
        SessionWord.objects.create(daily_session=session, word=w, order=i)
    return user, session


@patch("apps.learning.services.exam_deliver.send_quiz_poll")
def test_run_exam_sends_polls_and_records_questions(mock_poll, delivered_session):
    user, session = delivered_session
    mock_poll.side_effect = [f"poll-{i}" for i in range(10)]
    result = exam_deliver.run_exam(user.id)
    assert result is not None
    assert result.status == DailySession.Status.EXAM_SENT
    assert ExamQuestion.objects.filter(daily_session=session).count() == 3
    assert mock_poll.call_count == 3
    result.refresh_from_db()
    assert result.total == 3
    assert result.score == 0


@patch("apps.learning.services.exam_deliver.send_quiz_poll")
def test_run_exam_idempotent_after_exam_sent(mock_poll, delivered_session):
    user, session = delivered_session
    mock_poll.side_effect = [f"poll-{i}" for i in range(10)]
    exam_deliver.run_exam(user.id)
    mock_poll.reset_mock()
    again = exam_deliver.run_exam(user.id)   # session now EXAM_SENT
    assert again is None
    mock_poll.assert_not_called()


@patch("apps.learning.services.exam_deliver.send_quiz_poll")
def test_run_exam_none_when_not_delivered(mock_poll, delivered_session):
    user, session = delivered_session
    session.status = DailySession.Status.PENDING
    session.save()
    assert exam_deliver.run_exam(user.id) is None
    mock_poll.assert_not_called()
```

`apps/learning/tests/test_exam_tasks.py`:
```python
from unittest.mock import patch

import pytest

from apps.accounts.models import User
from apps.learning.models import LearningProfile
from apps.learning.tasks import dispatch_evening_exams

pytestmark = pytest.mark.django_db


@patch("apps.learning.tasks.is_due_for_exam")
@patch("apps.learning.tasks.send_exam")
def test_dispatch_evening_exams_enqueues_due(mock_send, mock_due):
    due = User.objects.create(first_name="Due")
    LearningProfile.objects.create(user=due, onboarded=True)
    skip = User.objects.create(first_name="Skip")
    LearningProfile.objects.create(user=skip, onboarded=True)
    mock_due.side_effect = lambda profile, now: profile.user_id == due.id

    dispatch_evening_exams()

    mock_send.delay.assert_called_once_with(due.id)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_run_exam.py apps/learning/tests/test_exam_tasks.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement `apps/learning/services/exam_deliver.py`**

```python
from django.conf import settings
from django.utils import timezone

from apps.learning.models import DailySession, ExamQuestion
from apps.learning.services.exam import build_questions, select_exam_words
from bot.sender import send_quiz_poll


def _local_date(profile):
    from zoneinfo import ZoneInfo

    return timezone.now().astimezone(ZoneInfo(profile.timezone)).date()


def run_exam(user_id: int) -> DailySession | None:
    session = (
        DailySession.objects.select_related("user__telegram")
        .filter(user_id=user_id, status=DailySession.Status.DELIVERED)
        .order_by("-date")
        .first()
    )
    if session is None:
        return None
    account = getattr(session.user, "telegram", None)
    if account is None or account.blocked_bot:
        return None

    words = select_exam_words(session, settings.EXAM_REVIEW_CAP)
    if not words:
        return None

    questions = build_questions(words)
    for q in questions:
        poll_id = send_quiz_poll(
            account.telegram_id, q["prompt"], q["options"], q["correct_option"], q["explanation"]
        )
        ExamQuestion.objects.create(
            daily_session=session,
            word=q["word"],
            question_type=q["question_type"],
            poll_id=poll_id,
            options=q["options"],
            correct_option=q["correct_option"],
        )

    session.status = DailySession.Status.EXAM_SENT
    session.exam_sent_at = timezone.now()
    session.total = len(questions)
    session.score = 0
    session.save(update_fields=["status", "exam_sent_at", "total", "score", "updated_at"])
    return session
```

- [ ] **Step 4: Add the Celery tasks to `apps/learning/tasks.py`**

Append (keep the existing delivery tasks; add the imports at the top):
```python
from apps.learning.services.exam_deliver import run_exam
from apps.learning.services.scheduling import is_due_for_exam


@shared_task
def send_exam(user_id: int) -> None:
    run_exam(user_id)


@shared_task
def dispatch_evening_exams() -> None:
    now = timezone.now()
    for profile in LearningProfile.objects.filter(is_active=True, onboarded=True).iterator():
        if is_due_for_exam(profile, now):
            send_exam.delay(profile.user_id)
```
(`timezone` and `LearningProfile` are already imported in `tasks.py` from Phase 2a.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_run_exam.py apps/learning/tests/test_exam_tasks.py -v`
Expected: all PASS.

- [ ] **Step 6: Full suite + commit**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/services/exam_deliver.py apps/learning/tasks.py apps/learning/tests/test_run_exam.py apps/learning/tests/test_exam_tasks.py
git commit -m "feat(learning): run_exam orchestration + dispatch_evening_exams"
```
Expected: all pass; ruff clean.

---

### Task 6: Poll-answer grading + bot handler

**Files:**
- Create: `apps/learning/services/exam_grade.py`
- Create: `bot/handlers/quiz.py`
- Modify: `bot/factory.py`
- Create: `apps/learning/tests/test_record_answer.py`, `bot/tests/test_handlers_quiz.py`

**Interfaces:**
- Consumes: `ExamQuestion`, `DailySession`, `grade_answer` (T2).
- Produces:
  - `apps.learning.services.exam_grade.record_answer(poll_id, option_ids) -> None` — sync: find the `ExamQuestion` by poll_id (skip if unknown/already answered), record `chosen_option`/`is_correct`/`answered_at`, apply SM-2 via `grade_answer`, and atomically `+1` the session score if correct.
  - `bot.handlers.quiz.router` (aiogram Router) with a `poll_answer` handler bridging to `record_answer` via `sync_to_async`; wired into `build_dispatcher`.

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_record_answer.py`:
```python
import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, ExamQuestion, WordProgress
from apps.learning.services.exam_grade import record_answer

pytestmark = pytest.mark.django_db


def _question(correct_option=1):
    user = User.objects.create(first_name="T")
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    session = DailySession.objects.create(
        user=user, date=timezone.now().date(), status=DailySession.Status.EXAM_SENT,
        total=1, score=0,
    )
    q = ExamQuestion.objects.create(
        daily_session=session, word=word, question_type=ExamQuestion.QType.EN_UZ,
        poll_id="poll-1", options=["a", "b", "c", "d"], correct_option=correct_option,
    )
    return user, word, session, q


def test_record_correct_answer_updates_all():
    user, word, session, q = _question(correct_option=1)
    record_answer("poll-1", [1])  # chose correct
    q.refresh_from_db()
    session.refresh_from_db()
    assert q.chosen_option == 1
    assert q.is_correct is True
    assert q.answered_at is not None
    assert session.score == 1
    assert WordProgress.objects.get(user=user, word=word).repetitions == 1


def test_record_wrong_answer_does_not_increment_score():
    user, word, session, q = _question(correct_option=1)
    record_answer("poll-1", [3])  # wrong
    q.refresh_from_db()
    session.refresh_from_db()
    assert q.is_correct is False
    assert session.score == 0
    assert WordProgress.objects.get(user=user, word=word).wrong_count == 1


def test_record_answer_idempotent_and_ignores_unknown():
    user, word, session, q = _question(correct_option=1)
    record_answer("poll-1", [1])
    record_answer("poll-1", [3])   # already answered → ignored
    session.refresh_from_db()
    assert session.score == 1      # not double-counted
    record_answer("unknown-poll", [0])  # no crash
```

`bot/tests/test_handlers_quiz.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import quiz

pytestmark = pytest.mark.asyncio


@patch("bot.handlers.quiz.record_answer")
async def test_poll_answer_handler_calls_record(mock_record):
    poll_answer = MagicMock()
    poll_answer.poll_id = "poll-1"
    poll_answer.option_ids = [2]
    await quiz.on_poll_answer(poll_answer)
    mock_record.assert_called_once_with("poll-1", [2])
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_record_answer.py bot/tests/test_handlers_quiz.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement `apps/learning/services/exam_grade.py`**

```python
from django.db.models import F
from django.utils import timezone

from apps.learning.models import DailySession, ExamQuestion
from apps.learning.services.srs import grade_answer


def record_answer(poll_id: str, option_ids: list[int]) -> None:
    """Record a poll answer, apply SM-2, and bump the session score if correct."""
    question = (
        ExamQuestion.objects.select_related("daily_session__user", "word")
        .filter(poll_id=poll_id)
        .first()
    )
    if question is None or question.chosen_option is not None:
        return
    if not option_ids:  # retracted vote
        return

    chosen = option_ids[0]
    question.chosen_option = chosen
    question.is_correct = chosen == question.correct_option
    question.answered_at = timezone.now()
    question.save(update_fields=["chosen_option", "is_correct", "answered_at", "updated_at"])

    grade_answer(question.daily_session.user, question.word, question.is_correct)
    if question.is_correct:
        DailySession.objects.filter(pk=question.daily_session_id).update(score=F("score") + 1)
```

- [ ] **Step 4: Implement the bot handler `bot/handlers/quiz.py`**

```python
from aiogram import Router
from aiogram.types import PollAnswer
from asgiref.sync import sync_to_async

from apps.learning.services.exam_grade import record_answer

router = Router()


@router.poll_answer()
async def on_poll_answer(poll_answer: PollAnswer) -> None:
    await sync_to_async(record_answer)(poll_answer.poll_id, poll_answer.option_ids)
```

- [ ] **Step 5: Wire the router into `bot/factory.py`**

In `bot/factory.py`, add `quiz` to the handlers import and include its router:
```python
from bot.handlers import common, onboarding, quiz, settings, start
```
and, in `build_dispatcher`, after the other `dp.include_router(...)` lines:
```python
    dp.include_router(quiz.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_record_answer.py bot/tests/test_handlers_quiz.py bot/tests/test_factory.py -v`
Expected: all PASS. (`test_factory.py`'s router-count assertion `>= 4` still holds with the 5th router.)

- [ ] **Step 7: Full suite + commit**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/services/exam_grade.py bot/handlers/quiz.py bot/factory.py apps/learning/tests/test_record_answer.py bot/tests/test_handlers_quiz.py
git commit -m "feat: poll-answer grading (SM-2 + score) + bot poll_answer handler"
```
Expected: all pass; ruff clean.

---

### Task 7: Finalize + daily report

**Files:**
- Create: `apps/learning/services/report.py`
- Modify: `apps/learning/tasks.py`
- Create: `apps/learning/tests/test_report.py`, `apps/learning/tests/test_finalize_tasks.py`

**Interfaces:**
- Consumes: `DailySession`, `ExamQuestion`, `send_daily` (Phase 2a sender), `EXAM_WINDOW_MINUTES`.
- Produces:
  - `apps.learning.services.report.build_report(session) -> str` — a summary string (score X/N, words to review).
  - `apps.learning.services.report.finalize_exam(session) -> None` — recompute score from correct answers, mark `completed`, send the report.
  - `apps.learning.tasks.finalize_due_exams()` (shared_task) — finalize every `exam_sent` session whose window has elapsed.

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_report.py`:
```python
import pytest
from django.utils import timezone

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, ExamQuestion
from apps.learning.services import report as report_mod

pytestmark = pytest.mark.django_db


def _session_with_answers():
    user = User.objects.create(first_name="T")
    TelegramAccount.objects.create(user=user, telegram_id=555)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    w1 = Word.objects.create(unit=unit, en="right", uz="a", order=1)
    w2 = Word.objects.create(unit=unit, en="wrong", uz="b", order=2)
    session = DailySession.objects.create(
        user=user, date=timezone.now().date(), status=DailySession.Status.EXAM_SENT, total=2,
    )
    ExamQuestion.objects.create(daily_session=session, word=w1, question_type="en_uz",
                                poll_id="p1", options=["a"], correct_option=0, is_correct=True)
    ExamQuestion.objects.create(daily_session=session, word=w2, question_type="en_uz",
                                poll_id="p2", options=["a"], correct_option=0, is_correct=False)
    return user, session


def test_build_report_shows_score_and_wrong_words():
    _, session = _session_with_answers()
    text = report_mod.build_report(session)
    assert "1/2" in text
    assert "wrong" in text  # the wrongly-answered word is listed for review


def test_finalize_exam_marks_completed_and_sends():
    from unittest.mock import patch
    user, session = _session_with_answers()
    with patch("apps.learning.services.report.send_daily") as mock_send:
        report_mod.finalize_exam(session)
    session.refresh_from_db()
    assert session.status == DailySession.Status.COMPLETED
    assert session.score == 1                 # recomputed from is_correct=True count
    assert session.completed_at is not None
    mock_send.assert_called_once()
```

`apps/learning/tests/test_finalize_tasks.py`:
```python
import datetime
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.learning.models import DailySession
from apps.learning.tasks import finalize_due_exams

pytestmark = pytest.mark.django_db


@patch("apps.learning.tasks.finalize_exam")
def test_finalize_due_exams_only_past_window(mock_finalize, settings):
    settings.EXAM_WINDOW_MINUTES = 60
    user = User.objects.create(first_name="T")
    old = DailySession.objects.create(
        user=user, date=timezone.now().date(), status=DailySession.Status.EXAM_SENT,
        exam_sent_at=timezone.now() - datetime.timedelta(minutes=90),
    )
    user2 = User.objects.create(first_name="T2")
    recent = DailySession.objects.create(
        user=user2, date=timezone.now().date(), status=DailySession.Status.EXAM_SENT,
        exam_sent_at=timezone.now() - datetime.timedelta(minutes=10),
    )
    finalize_due_exams()
    finalized_ids = [c.args[0].id for c in mock_finalize.call_args_list]
    assert old.id in finalized_ids
    assert recent.id not in finalized_ids
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_report.py apps/learning/tests/test_finalize_tasks.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement `apps/learning/services/report.py`**

```python
from django.utils import timezone

from apps.learning.models import DailySession, ExamQuestion
from bot.sender import send_daily


def build_report(session: DailySession) -> str:
    total = session.total or 0
    correct = ExamQuestion.objects.filter(daily_session=session, is_correct=True).count()
    wrong_words = list(
        ExamQuestion.objects.filter(daily_session=session, is_correct=False)
        .select_related("word")
        .values_list("word__en", flat=True)
    )
    unanswered = ExamQuestion.objects.filter(
        daily_session=session, chosen_option__isnull=True
    ).count()

    lines = [f"🏁 <b>Imtihon yakunlandi!</b>", f"Ball: <b>{correct}/{total}</b>"]
    if wrong_words:
        lines.append("🔁 Takrorlang: " + ", ".join(wrong_words))
    if unanswered:
        lines.append(f"⏭ Javob berilmadi: {unanswered} ta")
    lines.append("Barakalla, shu tarzda davom eting! 💪")
    return "\n".join(lines)


def finalize_exam(session: DailySession) -> None:
    session.score = ExamQuestion.objects.filter(daily_session=session, is_correct=True).count()
    session.status = DailySession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["score", "status", "completed_at", "updated_at"])

    account = getattr(session.user, "telegram", None)
    if account is not None and not account.blocked_bot:
        send_daily(account.telegram_id, None, [{"caption": build_report(session), "image": None, "audio": None}])
```

- [ ] **Step 4: Add the finalize task to `apps/learning/tasks.py`**

Append (add the import at the top):
```python
import datetime

from django.conf import settings

from apps.learning.services.report import finalize_exam


@shared_task
def finalize_due_exams() -> None:
    window = datetime.timedelta(minutes=settings.EXAM_WINDOW_MINUTES)
    cutoff = timezone.now() - window
    sessions = DailySession.objects.filter(
        status=DailySession.Status.EXAM_SENT, exam_sent_at__lte=cutoff
    ).select_related("user__telegram")
    for session in sessions.iterator():
        finalize_exam(session)
```
(`DailySession` is already imported in `tasks.py` — if not, add it.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_report.py apps/learning/tests/test_finalize_tasks.py -v`
Expected: all PASS.

- [ ] **Step 6: Full suite + commit**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/services/report.py apps/learning/tasks.py apps/learning/tests/test_report.py apps/learning/tests/test_finalize_tasks.py
git commit -m "feat(learning): finalize_exam + daily report + finalize_due_exams"
```
Expected: all pass; ruff clean.

---

### Task 8: Register Beat tasks + docs + gate

**Files:**
- Modify: `apps/learning/management/commands/setup_periodic_tasks.py`, `Readme.md`
- Modify: `apps/learning/tests/test_setup_periodic_tasks.py`

**Interfaces:**
- Produces: `setup_periodic_tasks` now also registers `dispatch_evening_exams` and `finalize_due_exams` (both 60s), in addition to `dispatch_morning_deliveries`.

- [ ] **Step 1: Extend the failing test**

Add to `apps/learning/tests/test_setup_periodic_tasks.py`:
```python
def test_setup_registers_exam_tasks():
    from django_celery_beat.models import PeriodicTask

    call_command("setup_periodic_tasks")
    assert PeriodicTask.objects.get(name="dispatch_evening_exams").task == (
        "apps.learning.tasks.dispatch_evening_exams"
    )
    assert PeriodicTask.objects.get(name="finalize_due_exams").task == (
        "apps.learning.tasks.finalize_due_exams"
    )
    # idempotent
    call_command("setup_periodic_tasks")
    assert PeriodicTask.objects.filter(name="dispatch_evening_exams").count() == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_setup_periodic_tasks.py -v`
Expected: FAIL — the new `test_setup_registers_exam_tasks` fails (tasks not registered).

- [ ] **Step 3: Extend the command**

In `apps/learning/management/commands/setup_periodic_tasks.py`, replace the single `update_or_create` with registration of all three, sharing the 60s schedule:
```python
    def handle(self, *args, **options):
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=60, period=IntervalSchedule.SECONDS
        )
        tasks = {
            "dispatch_morning_deliveries": "apps.learning.tasks.dispatch_morning_deliveries",
            "dispatch_evening_exams": "apps.learning.tasks.dispatch_evening_exams",
            "finalize_due_exams": "apps.learning.tasks.finalize_due_exams",
        }
        for name, task in tasks.items():
            PeriodicTask.objects.update_or_create(
                name=name, defaults={"interval": schedule, "task": task}
            )
        self.stdout.write(self.style.SUCCESS("periodic tasks registered"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_setup_periodic_tasks.py -v`
Expected: all PASS (the original `dispatch_morning_deliveries` test still passes).

- [ ] **Step 5: Update `Readme.md`**

In the "Daily delivery" section, extend the description to note the evening cycle:
```markdown
The `worker` + `beat` services also run the evening exam: at each user's
`exam_time`, `dispatch_evening_exams` sends native quiz polls over the day's
words (+ SRS-due reviews); the bot's poll-answer handler grades them and
updates each word's SM-2 schedule; `finalize_due_exams` closes the session
after `EXAM_WINDOW_MINUTES` and sends the daily report.
```

- [ ] **Step 6: Full gate + commit**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/management/commands/setup_periodic_tasks.py apps/learning/tests/test_setup_periodic_tasks.py Readme.md
git commit -m "feat(learning): register evening-exam Beat tasks + docs"
```
Expected: full suite passes; ruff clean.

---

## Self-Review (completed by plan author)

**Spec coverage** — every Phase 2b spec section maps to a task:
- §2 decisions (1 q/word round-robin, day+SRS-due scope, native quiz poll, SM-2, finalize window) → Tasks 2,3,4,5,7
- §3 model `ExamQuestion` + admin → Task 1
- §4 services (srs, exam questions, run_exam, report) → Tasks 2,3,5,7
- §5 scheduling (is_due_for_exam, dispatch, finalize) → Tasks 4,5,7,8
- §6 bot poll_answer + send_quiz_poll → Tasks 4,6
- §7 tests → each task ships tests; edges (poll sender, send_daily) mocked
- §8 config (EXAM_WINDOW_MINUTES, EXAM_REVIEW_CAP, beat registration) → Tasks 1,8
- §9 DoD → Task 8 gate

**Placeholder scan** — no TBD/TODO. One deliberate deviation from the spec is called out here: the spec §6 implies the poll's `open_period` equals the window, but Telegram caps `open_period` at 600s while `EXAM_WINDOW_MINUTES` defaults to 60 min; the plan therefore OMITS `open_period` (polls stay open) and relies on `finalize_due_exams` as the window boundary.

**Type/name consistency** — `apply_sm2`/`grade_answer` (T2) consumed by `record_answer` (T6); `select_exam_words`/`build_questions` (T3) consumed by `run_exam` (T5); `send_quiz_poll` (T4) consumed by `run_exam` (T5) and patched at `apps.learning.services.exam_deliver.send_quiz_poll`; `is_due_for_exam` (T4) consumed by `dispatch_evening_exams` (T5) and patched at `apps.learning.tasks.is_due_for_exam`; `record_answer` (T6) patched at `bot.handlers.quiz.record_answer`; `finalize_exam` (T7) patched at `apps.learning.tasks.finalize_exam`. `ExamQuestion.QType` values `en_uz`/`uz_en`/`def_word` used consistently. `DailySession.Status.EXAM_SENT`/`COMPLETED` (from Phase 2a) used consistently.

**Ordering note** — `docker compose up -d db redis` must be running for the DB-backed tests (Tasks 1,2,3,5,6,7,8).
```
