# Faza 2a — Ertalabki yetkazish (Morning Delivery) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically deliver each user's next batch of words at their configured time — a daily card image plus per-word messages (translation, image, combined EN+UZ audio) — advancing their position and recording a `DailySession`.

**Architecture:** A Celery Beat task (`dispatch_morning_deliveries`) runs every 60s, finds users due in their own timezone, and enqueues a per-user `deliver_daily_words` task. Delivery orchestration is a sync service (`run_delivery`) that selects the next words, advances position, generates a Pillow card + pydub-combined audio, and sends via a sync aiogram wrapper (`bot/sender.py`). All DB/media/logic is sync and unit-tested with mocks; only the thin Celery/aiogram edges are integration glue.

**Tech Stack:** Django 6 ORM (sync) · Celery + django-celery-beat · zoneinfo · Pillow · pydub + ffmpeg · gTTS · aiogram 3.x (`asyncio.run` wrapper) · pytest + pytest-django.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-03-phase-2a-morning-delivery-design.md`. Phases 0 + 1 are complete on `main`.
- Run via uv (pip-installed, not on PATH): `python -m uv run pytest`, `python -m uv run python manage.py ...`.
- Postgres + Redis run via `docker compose up -d db redis` (needed for DB tests).
- New models in `apps/learning`: `DailySession`, `SessionWord` (through), `WordProgress` — per spec §3. All inherit `apps.common.models.TimeStampedModel`; `WordProgress.created_at` serves as "first seen".
- Weekdays: `0=Monday … 6=Sunday`, matching `LearningProfile.study_weekdays`.
- **Sync everywhere; mock at the edges.** Services are sync Django ORM. Unit tests mock media (pydub/gTTS/Pillow) and the aiogram sender — no test hits ffmpeg, the network, or Telegram.
- Position order is global: `(unit.book.number, unit.number, word.order)`.
- Delivery is idempotent per `(user, date)` via `DailySession` `get_or_create`.
- Audio = native `Word.audio_en` (or gTTS EN fallback) + gTTS Uzbek, concatenated and repeated `audio_repeat` times, cached at `media/audio/combined/{book}/{unit}/{en}_r{repeat}.mp3`. Uzbek TTS is best-effort: if gTTS 'uz' fails, fall back to EN-only audio (never crash).
- Beat schedule registered via `python manage.py setup_periodic_tasks` (idempotent), not hardcoded.
- OUT of scope (Phase 2b): evening exam, quiz polls, SM-2 update logic, reports. (WordProgress rows are CREATED here with defaulted SM-2 fields; the update logic is 2b.)
- TDD; pristine output. Commit footer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

### Prerequisite (once, before Task 1)

```bash
git checkout main && git checkout -b phase-2a-morning-delivery
```

---

### Task 1: Models (DailySession, SessionWord, WordProgress) + admin + deps

**Files:**
- Modify: `apps/learning/models.py`, `apps/learning/admin.py`
- Create: `apps/learning/tests/test_delivery_models.py`
- Modify: `pyproject.toml` (add `pydub`), `Dockerfile` (add ffmpeg)
- Create (generated): `apps/learning/migrations/0002_*.py`

**Interfaces:**
- Produces: `apps.learning.models.DailySession` (user, date, book, unit, status, delivered_at, exam_sent_at, completed_at, score, total; `words` M2M through `SessionWord`), `apps.learning.models.SessionWord` (daily_session, word, order), `apps.learning.models.WordProgress` (user, word, status, repetitions, ease_factor, interval_days, next_review, correct_count, wrong_count, last_reviewed).

- [ ] **Step 1: Add pydub dependency and ffmpeg**

In `pyproject.toml` `[project] dependencies`, add:
```toml
    "pydub>=0.25",
```
In `Dockerfile`, add ffmpeg right after the `WORKDIR /app` line:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
```
Then: `python -m uv sync`

- [ ] **Step 2: Write the failing tests**

`apps/learning/tests/test_delivery_models.py`:
```python
import pytest
from django.db import IntegrityError

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, SessionWord, WordProgress

pytestmark = pytest.mark.django_db


def _user():
    return User.objects.create(first_name="T")


def _word():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    return Word.objects.create(unit=unit, en="afraid", uz="a", order=1)


def test_daily_session_unique_per_user_date():
    u = _user()
    DailySession.objects.create(user=u, date="2026-07-03")
    with pytest.raises(IntegrityError):
        DailySession.objects.create(user=u, date="2026-07-03")


def test_session_words_through_order():
    u = _user()
    w = _word()
    ds = DailySession.objects.create(user=u, date="2026-07-03")
    SessionWord.objects.create(daily_session=ds, word=w, order=1)
    assert list(ds.words.all()) == [w]


def test_word_progress_defaults_and_unique():
    u = _user()
    w = _word()
    wp = WordProgress.objects.create(user=u, word=w)
    assert wp.status == "new"
    assert wp.ease_factor == 2.5
    assert wp.repetitions == 0
    assert wp.interval_days == 0
    with pytest.raises(IntegrityError):
        WordProgress.objects.create(user=u, word=w)
```

- [ ] **Step 3: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_delivery_models.py -v`
Expected: FAIL — models don't exist.

- [ ] **Step 4: Add the models to `apps/learning/models.py`**

Append (keep the existing `LearningProfile`):
```python
class DailySession(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        EXAM_SENT = "exam_sent", "Exam sent"
        COMPLETED = "completed", "Completed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_sessions"
    )
    date = models.DateField()
    book = models.ForeignKey("catalog.Book", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    unit = models.ForeignKey("catalog.Unit", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    words = models.ManyToManyField("catalog.Word", through="SessionWord", related_name="daily_sessions")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    delivered_at = models.DateTimeField(null=True, blank=True)
    exam_sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    total = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("-date",)
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="uniq_user_daily_session")]

    def __str__(self) -> str:
        return f"DailySession(user={self.user_id}, {self.date})"


class SessionWord(models.Model):
    daily_session = models.ForeignKey(DailySession, on_delete=models.CASCADE, related_name="session_words")
    word = models.ForeignKey("catalog.Word", on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("order",)


class WordProgress(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        LEARNING = "learning", "Learning"
        KNOWN = "known", "Known"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="word_progress"
    )
    word = models.ForeignKey("catalog.Word", on_delete=models.CASCADE, related_name="progress")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    repetitions = models.PositiveSmallIntegerField(default=0)
    ease_factor = models.FloatField(default=2.5)
    interval_days = models.PositiveSmallIntegerField(default=0)
    next_review = models.DateField(null=True, blank=True)
    correct_count = models.PositiveSmallIntegerField(default=0)
    wrong_count = models.PositiveSmallIntegerField(default=0)
    last_reviewed = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "word"], name="uniq_user_word_progress")]

    def __str__(self) -> str:
        return f"WordProgress(user={self.user_id}, word={self.word_id})"
```
Ensure the top of the file imports `from django.conf import settings` (already present from `LearningProfile`).

- [ ] **Step 5: Make migrations and run tests**

Run:
```bash
python -m uv run python manage.py makemigrations learning
python -m uv run pytest apps/learning/tests/test_delivery_models.py -v
```
Expected: migration created; 3 tests PASS.

- [ ] **Step 6: Add admin**

In `apps/learning/admin.py`, add:
```python
from .models import DailySession, LearningProfile, WordProgress


@admin.register(DailySession)
class DailySessionAdmin(ModelAdmin):
    list_display = ("user", "date", "status", "score", "total", "delivered_at")
    list_filter = ("status", "date")
    raw_id_fields = ("user", "book", "unit")
    date_hierarchy = "date"


@admin.register(WordProgress)
class WordProgressAdmin(ModelAdmin):
    list_display = ("user", "word", "status", "repetitions", "ease_factor", "next_review")
    list_filter = ("status",)
    raw_id_fields = ("user", "word")
    search_fields = ("word__en",)
```
(Keep the existing `LearningProfileAdmin`; merge the import line with the existing `from .models import LearningProfile`.)

- [ ] **Step 7: Migrate, full suite, ruff, commit**

Run:
```bash
python -m uv run python manage.py migrate
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning pyproject.toml uv.lock Dockerfile
git commit -m "feat(learning): DailySession/SessionWord/WordProgress models + admin; add pydub+ffmpeg"
```
Expected: migrate clean; full suite passes (75 prior + 3 new = 78); ruff clean.

---

### Task 2: Word selection + position advance

**Files:**
- Create: `apps/learning/services/__init__.py`, `apps/learning/services/delivery.py`
- Create: `apps/learning/tests/test_delivery_selection.py`

**Interfaces:**
- Consumes: `apps.catalog.models.Word`, `LearningProfile`.
- Produces:
  - `apps.learning.services.delivery.next_words(profile, count) -> list[Word]` — the next `count` words after the profile's position in global order (no side effects).
  - `apps.learning.services.delivery.advance_position(profile, word) -> None` — set the profile's position to `word` and save.

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_delivery_selection.py`:
```python
import pytest

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import LearningProfile
from apps.learning.services.delivery import advance_position, next_words

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_units():
    b = Book.objects.create(number=1, title="B1", slug="b1")
    u1 = Unit.objects.create(book=b, number=1)
    u2 = Unit.objects.create(book=b, number=2)
    for i in range(1, 4):
        Word.objects.create(unit=u1, en=f"u1w{i}", uz=f"a{i}", order=i)
    for i in range(1, 4):
        Word.objects.create(unit=u2, en=f"u2w{i}", uz=f"b{i}", order=i)
    return b, u1, u2


def _profile(book, unit, order):
    u = User.objects.create(first_name="T")
    return LearningProfile.objects.create(
        user=u, current_book=book, current_unit=unit, current_word_order=order
    )


def test_next_words_from_start_of_unit(two_units):
    b, u1, u2 = two_units
    p = _profile(b, u1, 0)  # nothing delivered yet in unit 1
    words = next_words(p, 2)
    assert [w.en for w in words] == ["u1w1", "u1w2"]


def test_next_words_crosses_unit_boundary(two_units):
    b, u1, u2 = two_units
    p = _profile(b, u1, 2)  # last delivered = u1w2
    words = next_words(p, 2)
    assert [w.en for w in words] == ["u1w3", "u2w1"]


def test_next_words_empty_at_end(two_units):
    b, u1, u2 = two_units
    p = _profile(b, u2, 3)  # last word delivered
    assert next_words(p, 2) == []


def test_advance_position_sets_to_word(two_units):
    b, u1, u2 = two_units
    p = _profile(b, u1, 0)
    w = Word.objects.get(en="u2w1")
    advance_position(p, w)
    p.refresh_from_db()
    assert p.current_unit_id == u2.id
    assert p.current_word_order == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_delivery_selection.py -v`
Expected: FAIL — `apps.learning.services.delivery` missing.

- [ ] **Step 3: Implement `apps/learning/services/delivery.py`**

`apps/learning/services/__init__.py`: (empty)

`apps/learning/services/delivery.py`:
```python
from django.db.models import Q

from apps.catalog.models import Word
from apps.learning.models import LearningProfile

_ORDER = ("unit__book__number", "unit__number", "order")


def next_words(profile: LearningProfile, count: int) -> list[Word]:
    """Return the next `count` words after the profile's position, in global order."""
    qs = Word.objects.select_related("unit__book")
    if profile.current_unit_id is not None:
        unit = profile.current_unit
        bn, un, order = unit.book.number, unit.number, profile.current_word_order
        after = (
            Q(unit__book__number__gt=bn)
            | (Q(unit__book__number=bn) & Q(unit__number__gt=un))
            | (Q(unit__book__number=bn) & Q(unit__number=un) & Q(order__gt=order))
        )
        qs = qs.filter(after)
    return list(qs.order_by(*_ORDER)[:count])


def advance_position(profile: LearningProfile, word: Word) -> None:
    """Move the profile's position to `word`."""
    profile.current_book = word.unit.book
    profile.current_unit = word.unit
    profile.current_word_order = word.order
    profile.save(update_fields=["current_book", "current_unit", "current_word_order", "updated_at"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_delivery_selection.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/learning/services apps/learning/tests/test_delivery_selection.py
git commit -m "feat(learning): next_words selection + advance_position (global order)"
```

---

### Task 3: Due-check logic

**Files:**
- Create: `apps/learning/services/scheduling.py`
- Create: `apps/learning/tests/test_scheduling.py`

**Interfaces:**
- Consumes: `LearningProfile`.
- Produces: `apps.learning.services.scheduling.is_due_for_delivery(profile, now_utc: datetime) -> bool` — True iff the profile is active+onboarded, today (in its timezone) is a study weekday, and the local time's hour:minute equals `morning_time`.

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_scheduling.py`:
```python
import datetime
from unittest.mock import MagicMock

from apps.learning.services.scheduling import is_due_for_delivery


def _profile(**kw):
    p = MagicMock()
    p.is_active = kw.get("is_active", True)
    p.onboarded = kw.get("onboarded", True)
    p.timezone = kw.get("timezone", "Asia/Tashkent")
    p.study_weekdays = kw.get("study_weekdays", [0, 1, 2, 3, 4, 5, 6])
    p.morning_time = kw.get("morning_time", datetime.time(7, 0))
    return p


def _utc(y, m, d, hh, mm):
    return datetime.datetime(y, m, d, hh, mm, tzinfo=datetime.UTC)


def test_due_when_local_time_matches():
    # Asia/Tashkent = UTC+5; 02:00 UTC = 07:00 local. 2026-07-06 is a Monday (weekday 0).
    assert is_due_for_delivery(_profile(), _utc(2026, 7, 6, 2, 0)) is True


def test_not_due_off_by_a_minute():
    assert is_due_for_delivery(_profile(), _utc(2026, 7, 6, 2, 1)) is False


def test_not_due_on_non_study_weekday():
    # study only on weekday 2 (Wednesday); 2026-07-06 is Monday.
    assert is_due_for_delivery(_profile(study_weekdays=[2]), _utc(2026, 7, 6, 2, 0)) is False


def test_not_due_when_inactive_or_not_onboarded():
    assert is_due_for_delivery(_profile(is_active=False), _utc(2026, 7, 6, 2, 0)) is False
    assert is_due_for_delivery(_profile(onboarded=False), _utc(2026, 7, 6, 2, 0)) is False
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_scheduling.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/learning/services/scheduling.py`**

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from apps.learning.models import LearningProfile


def is_due_for_delivery(profile: LearningProfile, now_utc: datetime) -> bool:
    """True if this profile should receive its morning delivery at `now_utc`."""
    if not profile.is_active or not profile.onboarded:
        return False
    local = now_utc.astimezone(ZoneInfo(profile.timezone))
    if local.weekday() not in profile.study_weekdays:
        return False
    return local.hour == profile.morning_time.hour and local.minute == profile.morning_time.minute
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_scheduling.py -v`
Expected: 4 tests PASS. (Verify the weekday arithmetic: 2026-07-06 is a Monday.)

- [ ] **Step 5: Commit**

```bash
git add apps/learning/services/scheduling.py apps/learning/tests/test_scheduling.py
git commit -m "feat(learning): timezone-aware is_due_for_delivery"
```

---

### Task 4: Daily card rendering

**Files:**
- Create: `apps/learning/services/cards.py`
- Create: `apps/learning/tests/test_cards.py`

**Interfaces:**
- Produces: `apps.learning.services.cards.render_daily_card(words, date) -> bytes` — a PNG image (bytes) tabulating the day's words (English, Uzbek, part of speech).

- [ ] **Step 1: Write the failing test**

`apps/learning/tests/test_cards.py`:
```python
import datetime

import pytest

from apps.catalog.models import Book, Unit, Word
from apps.learning.services.cards import render_daily_card

pytestmark = pytest.mark.django_db


def test_render_daily_card_returns_png_bytes():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    words = [
        Word.objects.create(unit=unit, en="afraid", uz="qo'rqib", part_of_speech="adj.", order=1),
        Word.objects.create(unit=unit, en="agree", uz="rozi", part_of_speech="v.", order=2),
    ]
    data = render_daily_card(words, datetime.date(2026, 7, 6))
    assert isinstance(data, bytes) and len(data) > 100
    assert data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic number
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_cards.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/learning/services/cards.py`**

```python
import datetime
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from apps.catalog.models import Word

_ROW_H = 40
_PAD = 20
_WIDTH = 720


def render_daily_card(words: list[Word], date: datetime.date) -> bytes:
    """Render a simple table card (English | Uzbek | POS) as PNG bytes."""
    height = _PAD * 2 + _ROW_H * (len(words) + 1)
    img = Image.new("RGB", (_WIDTH, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    draw.text((_PAD, _PAD), f"Bugungi so'zlar — {date:%d.%m.%Y}", fill="black", font=font)
    y = _PAD + _ROW_H
    for i, word in enumerate(words, start=1):
        line = f"{i}. {word.en}  —  {word.uz}   {word.part_of_speech}"
        draw.text((_PAD, y), line, fill="black", font=font)
        y += _ROW_H

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m uv run pytest apps/learning/tests/test_cards.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/learning/services/cards.py apps/learning/tests/test_cards.py
git commit -m "feat(learning): render_daily_card (Pillow word table)"
```

---

### Task 5: Combined audio building + cache

**Files:**
- Create: `apps/learning/services/audio.py`
- Create: `apps/learning/tests/test_audio.py`

**Interfaces:**
- Consumes: `Word`, `apps.common.tts` (gTTS fallback).
- Produces: `apps.learning.services.audio.build_word_audio(word, repeat) -> bytes` — MP3 bytes of (EN + UZ) repeated `repeat` times, cached on disk; reuses the cache on subsequent calls. Uzbek is best-effort (EN-only if it fails).

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_audio.py`:
```python
from unittest.mock import patch

import pytest

from apps.catalog.models import Book, Unit, Word
from apps.learning.services import audio as audio_mod

pytestmark = pytest.mark.django_db


@pytest.fixture
def word(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    return Word.objects.create(unit=unit, en="afraid", uz="qo'rqib", order=1)


def test_build_word_audio_renders_and_caches(word):
    with patch.object(audio_mod, "_render_combined", return_value=b"MP3DATA") as render:
        first = audio_mod.build_word_audio(word, 2)
        assert first == b"MP3DATA"
        render.assert_called_once_with(word, 2)
        # second call hits the cache, no re-render
        render.reset_mock()
        second = audio_mod.build_word_audio(word, 2)
        assert second == b"MP3DATA"
        render.assert_not_called()


def test_cache_path_differs_by_repeat(word):
    p1 = audio_mod._combined_path(word, 1)
    p2 = audio_mod._combined_path(word, 2)
    assert p1 != p2
    assert p1.name.endswith("_r1.mp3")
    assert p2.name.endswith("_r2.mp3")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_audio.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/learning/services/audio.py`**

```python
import logging
from io import BytesIO
from pathlib import Path

from django.conf import settings
from pydub import AudioSegment

from apps.catalog.models import Word
from apps.common.tts import get_tts_provider

logger = logging.getLogger(__name__)


def _combined_path(word: Word, repeat: int) -> Path:
    return (
        Path(settings.MEDIA_ROOT)
        / "audio"
        / "combined"
        / str(word.unit.book.number)
        / str(word.unit.number)
        / f"{word.en}_r{repeat}.mp3"
    )


def build_word_audio(word: Word, repeat: int) -> bytes:
    """Combined EN+UZ audio repeated `repeat` times, cached on disk."""
    path = _combined_path(word, repeat)
    if path.exists():
        return path.read_bytes()
    data = _render_combined(word, repeat)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def _english_segment(word: Word) -> AudioSegment:
    if word.audio_en:
        return AudioSegment.from_file(word.audio_en.path)
    provider = get_tts_provider()
    return AudioSegment.from_file(BytesIO(provider.synthesize(word.en, lang="en")), format="mp3")


def _uzbek_segment(word: Word) -> AudioSegment | None:
    try:
        provider = get_tts_provider()
        return AudioSegment.from_file(BytesIO(provider.synthesize(word.uz, lang="uz")), format="mp3")
    except Exception as exc:  # gTTS 'uz' may be unsupported; degrade to EN-only
        logger.warning("uz audio failed for %s: %s", word.en, exc)
        return None


def _render_combined(word: Word, repeat: int) -> bytes:
    en = _english_segment(word)
    uz = _uzbek_segment(word)
    one = en if uz is None else en + uz
    combined = one * max(1, repeat)
    buf = BytesIO()
    combined.export(buf, format="mp3")
    return buf.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_audio.py -v`
Expected: both tests PASS (they patch `_render_combined`, so no ffmpeg is invoked).

- [ ] **Step 5: Commit**

```bash
git add apps/learning/services/audio.py apps/learning/tests/test_audio.py
git commit -m "feat(learning): build_word_audio (EN+UZ combined, cached, gtts-uz best-effort)"
```

---

### Task 6: Telegram sender (sync aiogram wrapper)

**Files:**
- Create: `bot/sender.py`
- Create: `bot/tests/test_sender.py`

**Interfaces:**
- Consumes: `bot.config.get_bot_token`, aiogram.
- Produces:
  - `bot.sender.send_daily(chat_id: int, card: bytes | None, items: list[dict]) -> None` — sends the card photo (if any) then each item; each `item` is `{"caption": str, "image": bytes | None, "audio": bytes | None}`.
  - `bot.sender._send_daily(bot, chat_id, card, items)` — the async worker (tested directly).

- [ ] **Step 1: Write the failing test**

`bot/tests/test_sender.py`:
```python
from unittest.mock import AsyncMock

import pytest

from bot import sender

pytestmark = pytest.mark.asyncio


async def test_send_daily_sends_card_then_items():
    bot = AsyncMock()
    items = [
        {"caption": "afraid — qo'rqib", "image": b"IMG", "audio": b"AUD"},
        {"caption": "agree — rozi", "image": None, "audio": None},
    ]
    await sender._send_daily(bot, 555, b"CARD", items)

    # 1 card photo + 1 word photo (item 1) = 2 send_photo; item 2 has no image → send_message
    assert bot.send_photo.await_count == 2
    assert bot.send_message.await_count == 1
    assert bot.send_audio.await_count == 1  # only item 1 has audio


async def test_send_daily_no_card():
    bot = AsyncMock()
    await sender._send_daily(bot, 555, None, [{"caption": "x", "image": None, "audio": None}])
    assert bot.send_photo.await_count == 0
    assert bot.send_message.await_count == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_sender.py -v`
Expected: FAIL — `bot.sender` missing.

- [ ] **Step 3: Implement `bot/sender.py`**

```python
import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile

from bot.config import get_bot_token


def _make_bot() -> Bot:
    return Bot(token=get_bot_token(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def _send_daily(bot: Bot, chat_id: int, card: bytes | None, items: list[dict]) -> None:
    if card:
        await bot.send_photo(chat_id, BufferedInputFile(card, "card.png"))
    for item in items:
        if item.get("image"):
            await bot.send_photo(
                chat_id, BufferedInputFile(item["image"], "word.jpg"), caption=item["caption"]
            )
        else:
            await bot.send_message(chat_id, item["caption"])
        if item.get("audio"):
            await bot.send_audio(chat_id, BufferedInputFile(item["audio"], "word.mp3"))


def send_daily(chat_id: int, card: bytes | None, items: list[dict]) -> None:
    async def _run() -> None:
        bot = _make_bot()
        try:
            await _send_daily(bot, chat_id, card, items)
        finally:
            await bot.session.close()

    asyncio.run(_run())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_sender.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/sender.py bot/tests/test_sender.py
git commit -m "feat(bot): sync send_daily wrapper (card + per-word photo/audio)"
```

---

### Task 7: Delivery orchestration + Celery tasks

**Files:**
- Create: `apps/learning/services/deliver.py`
- Create: `apps/learning/tasks.py`
- Create: `apps/learning/tests/test_deliver.py`, `apps/learning/tests/test_tasks.py`

**Interfaces:**
- Consumes: `next_words`/`advance_position` (T2), `is_due_for_delivery` (T3), `render_daily_card` (T4), `build_word_audio` (T5), `bot.sender.send_daily` (T6), models (T1).
- Produces:
  - `apps.learning.services.deliver.run_delivery(user_id) -> DailySession | None` — idempotent per (user, local date); selects words, advances position, creates `DailySession`+`SessionWord`+`WordProgress`, renders+sends, marks delivered. Returns None if not due-eligible / already delivered / no content.
  - `apps.learning.tasks.deliver_daily_words(user_id)` (shared_task wrapping `run_delivery`), `apps.learning.tasks.dispatch_morning_deliveries()` (shared_task).

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_deliver.py`:
```python
import datetime
from unittest.mock import patch

import pytest

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, LearningProfile, WordProgress
from apps.learning.services import deliver as deliver_mod

pytestmark = pytest.mark.django_db


@pytest.fixture
def user_with_words():
    user = User.objects.create(first_name="T")
    TelegramAccount.objects.create(user=user, telegram_id=555)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    for i in range(1, 6):
        Word.objects.create(unit=unit, en=f"w{i}", uz=f"t{i}", order=i)
    LearningProfile.objects.create(
        user=user, onboarded=True, words_per_session=3,
        current_book=book, current_unit=unit, current_word_order=0,
    )
    return user, book, unit


@patch("apps.learning.services.deliver.send_daily")
@patch("apps.learning.services.deliver.build_word_audio", return_value=b"AUD")
@patch("apps.learning.services.deliver.render_daily_card", return_value=b"CARD")
def test_run_delivery_creates_session_and_advances(mock_card, mock_audio, mock_send, user_with_words):
    user, book, unit = user_with_words
    session = deliver_mod.run_delivery(user.id)
    assert session is not None
    assert session.status == DailySession.Status.DELIVERED
    assert list(session.words.values_list("en", flat=True)) == ["w1", "w2", "w3"]
    assert WordProgress.objects.filter(user=user).count() == 3
    user.learning_profile.refresh_from_db()
    assert user.learning_profile.current_word_order == 3  # advanced to last delivered
    mock_send.assert_called_once()


@patch("apps.learning.services.deliver.send_daily")
@patch("apps.learning.services.deliver.build_word_audio", return_value=b"AUD")
@patch("apps.learning.services.deliver.render_daily_card", return_value=b"CARD")
def test_run_delivery_is_idempotent(mock_card, mock_audio, mock_send, user_with_words):
    user, book, unit = user_with_words
    deliver_mod.run_delivery(user.id)
    mock_send.reset_mock()
    again = deliver_mod.run_delivery(user.id)  # same day → already delivered
    assert again is None
    mock_send.assert_not_called()
    assert DailySession.objects.filter(user=user).count() == 1


@patch("apps.learning.services.deliver.send_daily")
def test_run_delivery_no_content_sends_nothing(mock_send, user_with_words):
    user, book, unit = user_with_words
    p = user.learning_profile
    p.current_word_order = 5  # past the last word
    p.save()
    assert deliver_mod.run_delivery(user.id) is None
    mock_send.assert_not_called()
```

`apps/learning/tests/test_tasks.py`:
```python
from unittest.mock import patch

import pytest

from apps.accounts.models import User
from apps.learning.models import LearningProfile
from apps.learning.tasks import dispatch_morning_deliveries

pytestmark = pytest.mark.django_db


@patch("apps.learning.tasks.is_due_for_delivery")
@patch("apps.learning.tasks.deliver_daily_words")
def test_dispatch_enqueues_only_due_users(mock_deliver, mock_due):
    due_user = User.objects.create(first_name="Due")
    LearningProfile.objects.create(user=due_user, onboarded=True)
    skip_user = User.objects.create(first_name="Skip")
    LearningProfile.objects.create(user=skip_user, onboarded=True)

    mock_due.side_effect = lambda profile, now: profile.user_id == due_user.id

    dispatch_morning_deliveries()

    mock_deliver.delay.assert_called_once_with(due_user.id)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_deliver.py apps/learning/tests/test_tasks.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement `apps/learning/services/deliver.py`**

```python
from django.utils import timezone

from apps.learning.models import DailySession, LearningProfile, SessionWord, WordProgress
from apps.learning.services.cards import render_daily_card
from apps.learning.services.delivery import advance_position, next_words
from apps.learning.services.audio import build_word_audio
from bot.sender import send_daily


def _local_date(profile: LearningProfile):
    from zoneinfo import ZoneInfo

    return timezone.now().astimezone(ZoneInfo(profile.timezone)).date()


def _caption(word) -> str:
    parts = [f"<b>{word.en}</b> {word.part_of_speech}".strip()]
    if word.pronunciation:
        parts.append(word.pronunciation)
    parts.append(f"🇺🇿 {word.uz}")
    if word.definition:
        parts.append(f"\n<i>{word.definition}</i>")
    if word.example:
        parts.append(word.example)
    return "\n".join(parts)


def run_delivery(user_id: int) -> DailySession | None:
    profile = (
        LearningProfile.objects.select_related("user", "current_unit__book")
        .filter(user_id=user_id, is_active=True, onboarded=True)
        .first()
    )
    if profile is None:
        return None
    account = getattr(profile.user, "telegram", None)
    if account is None or account.blocked_bot:
        return None

    date = _local_date(profile)
    session, created = DailySession.objects.get_or_create(
        user_id=user_id, date=date, defaults={"book": profile.current_book, "unit": profile.current_unit}
    )
    if session.status == DailySession.Status.DELIVERED:
        return None

    words = next_words(profile, profile.words_per_session)
    if not words:
        send_daily(account.telegram_id, None, [{"caption": "🎉 Tabriklaymiz! Barcha so'zlarni tugatdingiz.", "image": None, "audio": None}])
        session.status = DailySession.Status.DELIVERED
        session.delivered_at = timezone.now()
        session.save(update_fields=["status", "delivered_at", "updated_at"])
        return session

    items = []
    for order, word in enumerate(words, start=1):
        SessionWord.objects.get_or_create(daily_session=session, word=word, defaults={"order": order})
        WordProgress.objects.get_or_create(user_id=user_id, word=word)
        image = word.image.read() if word.image else None
        audio = build_word_audio(word, profile.audio_repeat) if profile.audio_enabled else None
        items.append({"caption": _caption(word), "image": image, "audio": audio})

    card = render_daily_card(words, date)
    send_daily(account.telegram_id, card, items)

    advance_position(profile, words[-1])
    session.status = DailySession.Status.DELIVERED
    session.delivered_at = timezone.now()
    session.save(update_fields=["status", "delivered_at", "updated_at"])
    return session
```

- [ ] **Step 4: Implement `apps/learning/tasks.py`**

```python
from celery import shared_task
from django.utils import timezone

from apps.learning.models import LearningProfile
from apps.learning.services.deliver import run_delivery
from apps.learning.services.scheduling import is_due_for_delivery


@shared_task
def deliver_daily_words(user_id: int) -> None:
    run_delivery(user_id)


@shared_task
def dispatch_morning_deliveries() -> None:
    now = timezone.now()
    profiles = LearningProfile.objects.filter(is_active=True, onboarded=True)
    for profile in profiles.iterator():
        if is_due_for_delivery(profile, now):
            deliver_daily_words.delay(profile.user_id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_deliver.py apps/learning/tests/test_tasks.py -v`
Expected: all PASS.

- [ ] **Step 6: Full suite + commit**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/services/deliver.py apps/learning/tasks.py apps/learning/tests/test_deliver.py apps/learning/tests/test_tasks.py
git commit -m "feat(learning): run_delivery orchestration + dispatch/deliver Celery tasks"
```
Expected: all pass; ruff clean.

---

### Task 8: Beat registration command + docs + gate

**Files:**
- Create: `apps/learning/management/__init__.py`, `apps/learning/management/commands/__init__.py`, `apps/learning/management/commands/setup_periodic_tasks.py`
- Create: `apps/learning/tests/test_setup_periodic_tasks.py`
- Modify: `Readme.md`

**Interfaces:**
- Consumes: `django_celery_beat.models`.
- Produces: `python manage.py setup_periodic_tasks` — idempotently registers a 60-second interval `PeriodicTask` running `apps.learning.tasks.dispatch_morning_deliveries`.

- [ ] **Step 1: Write the failing test**

`apps/learning/tests/test_setup_periodic_tasks.py`:
```python
import pytest
from django.core.management import call_command
from django_celery_beat.models import PeriodicTask

pytestmark = pytest.mark.django_db


def test_setup_registers_dispatch_task():
    call_command("setup_periodic_tasks")
    task = PeriodicTask.objects.get(name="dispatch_morning_deliveries")
    assert task.task == "apps.learning.tasks.dispatch_morning_deliveries"
    assert task.interval.every == 60
    # idempotent
    call_command("setup_periodic_tasks")
    assert PeriodicTask.objects.filter(name="dispatch_morning_deliveries").count() == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_setup_periodic_tasks.py -v`
Expected: FAIL — `Unknown command: 'setup_periodic_tasks'`.

- [ ] **Step 3: Implement the command**

Create empty `apps/learning/management/__init__.py` and `apps/learning/management/commands/__init__.py`.

`apps/learning/management/commands/setup_periodic_tasks.py`:
```python
from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Register the recurring Celery Beat tasks (idempotent)."

    def handle(self, *args, **options):
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=60, period=IntervalSchedule.SECONDS
        )
        PeriodicTask.objects.update_or_create(
            name="dispatch_morning_deliveries",
            defaults={
                "interval": schedule,
                "task": "apps.learning.tasks.dispatch_morning_deliveries",
            },
        )
        self.stdout.write(self.style.SUCCESS("periodic tasks registered"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m uv run pytest apps/learning/tests/test_setup_periodic_tasks.py -v`
Expected: PASS.

- [ ] **Step 5: Update `Readme.md`**

Add to the "Bot (Telegram)" section (or a new "Daily delivery" subsection):
```markdown
## Daily delivery (Phase 2a)

After migrating, register the recurring Beat task once:

```bash
python -m uv run python manage.py setup_periodic_tasks
```

The `worker` + `beat` compose services then deliver each user's words at their
configured `morning_time` (on their `study_weekdays`, in their timezone).
Audio combining needs `ffmpeg` (bundled in the Docker image; install locally if
running the worker outside Docker).
```

- [ ] **Step 6: Full gate + commit**

Run:
```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/management apps/learning/tests/test_setup_periodic_tasks.py Readme.md
git commit -m "feat(learning): setup_periodic_tasks command + delivery docs"
```
Expected: full suite passes; ruff clean.

---

## Self-Review (completed by plan author)

**Spec coverage** — every Phase 2a spec section maps to a task:
- §2 decisions (beat 60s, card+per-word, EN+UZ pydub audio, sync sender, idempotent, blocked-user) → Tasks 3,4,5,6,7
- §3 models (DailySession/SessionWord/WordProgress) → Task 1
- §4 scheduling engine (dispatch + is_due + beat registration) → Tasks 3,7,8
- §5 delivery flow (session, select, media, send, mark) → Task 7 (+4,5,6)
- §6 selection + position → Task 2
- §7 tests → each task ships tests; edges mocked per Global Constraints
- §8 config/Docker (ffmpeg, pydub, setup command) → Tasks 1,8
- §9 DoD → Task 8 gate

**Placeholder scan** — no TBD/TODO/"add error handling"; the two real risks (gTTS-uz support, real Telegram send) are handled explicitly (best-effort UZ fallback; mocked sender + token-gated live send) rather than left vague.

**Type/name consistency** — `next_words`/`advance_position` (T2), `is_due_for_delivery` (T3), `render_daily_card` (T4), `build_word_audio` (T5), `send_daily`/`_send_daily` (T6) are consumed with matching signatures in `run_delivery` (T7); the tasks patch these at `apps.learning.services.deliver.<name>` (import site), matching the imports in `deliver.py`. `DailySession.Status.DELIVERED` is used consistently. Handler/edge tests mock media + sender (no ffmpeg, no network) per Global Constraints.

**Ordering note** — `docker compose up -d db redis` must be running for the DB-backed tests (Tasks 1,2,4,5,7,8).
