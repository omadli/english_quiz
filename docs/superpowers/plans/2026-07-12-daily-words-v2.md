# Daily Words v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the daily-words experience — hideable menu, clearer settings with voice choice, free multi-voice TTS (edge-tts), a single-message + single-audio morning delivery, and a "Batafsil" deep-link into the Mini App's existing today tab.

**Architecture:** edge-tts becomes a new pluggable `TTSProvider` (voice-aware). The morning delivery builds ONE combined audio (per word: EN×repeat → UZ) with the word list as caption + an inline WebApp "Batafsil" button. Settings (bot + Mini App) gain EN/UZ voice + repeat pickers, backed by two new `LearningProfile` fields.

**Tech Stack:** Python 3.13, Django 6, aiogram 3.x, pydub+ffmpeg, edge-tts, pytest.

## Global Constraints

- `ruff check .` must pass; line-length 100.
- Tests: `python -m uv run pytest` (Docker Postgres must be up: `docker compose up -d db`). Run ONE pytest process at a time.
- TDD: failing test → minimal code → pass → commit. Frequent commits.
- Do NOT run a live bot locally (prod is on webhook; local polling deletes the prod webhook). Verify via pytest only.
- Reuse existing helpers: `_word_payload`, `_profile_from_request`, `_clean_settings` (`apps/catalog/views.py`); `get_tts_provider` (`apps/common/tts.py`); `wordCard`/`setTab` (SPA).
- Uzbek has exactly TWO edge-tts voices (`uz-UZ-MadinaNeural`, `uz-UZ-SardorNeural`); do not invent more.
- Work on branch `daily-words-v2`; do not push to `main` until the whole sub-project passes (push = prod deploy).

---

### Task 1: Menu keyboard — hideable + drop two buttons

**Files:**
- Modify: `bot/keyboards/menu.py`
- Test: `bot/tests/test_keyboards_menu.py` (create)

**Interfaces:**
- Produces: `main_menu_keyboard(webapp_url: str | None = None) -> ReplyKeyboardMarkup` (unchanged signature; `one_time_keyboard=True`, no `MENU_GROUP_QUIZ`/`MENU_TOP`).

- [ ] **Step 1: Write the failing test**

```python
# bot/tests/test_keyboards_menu.py
from bot import strings
from bot.keyboards.menu import main_menu_keyboard


def _texts(kb):
    return [b.text for row in kb.keyboard for b in row]


def test_menu_is_one_time_and_not_persistent():
    kb = main_menu_keyboard(None)
    assert kb.one_time_keyboard is True
    assert not kb.is_persistent
    assert kb.resize_keyboard is True


def test_menu_drops_group_quiz_and_top():
    texts = _texts(main_menu_keyboard(None))
    assert strings.MENU_GROUP_QUIZ not in texts
    assert strings.MENU_TOP not in texts
    # core buttons still present
    for t in (strings.MENU_TODAY, strings.MENU_EXAM, strings.MENU_TEST,
              strings.MENU_WORDS, strings.MENU_BOOKS, strings.MENU_SETTINGS):
        assert t in texts


def test_menu_adds_webapp_button_when_url_set():
    assert strings.MENU_WEBAPP in _texts(main_menu_keyboard("https://x/webapp/"))
    assert strings.MENU_WEBAPP not in _texts(main_menu_keyboard(None))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest bot/tests/test_keyboards_menu.py -v`
Expected: FAIL (`one_time_keyboard is False`; group-quiz/top still present).

- [ ] **Step 3: Implement**

```python
# bot/keyboards/menu.py
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from bot import strings


def main_menu_keyboard(webapp_url: str | None = None) -> ReplyKeyboardMarkup:
    """Bottom menu. `one_time_keyboard` so it collapses after a tap instead of
    permanently filling the screen. WebApp button only when a (https) URL is set."""
    rows = [
        [KeyboardButton(text=strings.MENU_TODAY), KeyboardButton(text=strings.MENU_EXAM)],
        [KeyboardButton(text=strings.MENU_TEST), KeyboardButton(text=strings.MENU_WORDS)],
        [KeyboardButton(text=strings.MENU_BOOKS), KeyboardButton(text=strings.MENU_SETTINGS)],
    ]
    if webapp_url:
        rows.append([KeyboardButton(text=strings.MENU_WEBAPP, web_app=WebAppInfo(url=webapp_url))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)
```

(Leave the `MENU_TOP`/`MENU_GROUP_QUIZ` message handlers in `bot/handlers/menu.py` — `/top` and group flows stay reachable; only the buttons are gone.)

- [ ] **Step 4: Run tests**

Run: `python -m uv run pytest bot/tests/test_keyboards_menu.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add bot/keyboards/menu.py bot/tests/test_keyboards_menu.py
git commit -m "feat(bot): one_time menu keyboard; drop Group Quiz + Reyting buttons"
```

---

### Task 2: LearningProfile voice fields

**Files:**
- Modify: `apps/learning/models.py:19-36` (add two fields)
- Create: `apps/learning/migrations/000X_profile_voices.py` (via makemigrations)
- Test: `apps/learning/tests/test_models.py` (append)

**Interfaces:**
- Produces: `LearningProfile.en_voice: str` (default `"en-US-AriaNeural"`), `LearningProfile.uz_voice: str` (default `"uz-UZ-MadinaNeural"`).

- [ ] **Step 1: Write the failing test**

```python
# apps/learning/tests/test_models.py  (append)
import pytest
from apps.accounts.models import User
from apps.learning.models import LearningProfile


@pytest.mark.django_db
def test_profile_voice_defaults():
    p = LearningProfile.objects.create(user=User.objects.create(first_name="V"))
    assert p.en_voice == "en-US-AriaNeural"
    assert p.uz_voice == "uz-UZ-MadinaNeural"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest apps/learning/tests/test_models.py::test_profile_voice_defaults -v`
Expected: FAIL (`AttributeError`/no such field).

- [ ] **Step 3: Add fields + migration**

In `apps/learning/models.py`, inside `LearningProfile` after `audio_repeat`:

```python
    en_voice = models.CharField(max_length=40, default="en-US-AriaNeural")
    uz_voice = models.CharField(max_length=40, default="uz-UZ-MadinaNeural")
```

Generate the migration:

```bash
docker compose up -d db
python -m uv run python manage.py makemigrations learning
```

- [ ] **Step 4: Run tests**

Run: `python -m uv run pytest apps/learning/tests/test_models.py::test_profile_voice_defaults -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/learning/models.py apps/learning/migrations/ apps/learning/tests/test_models.py
git commit -m "feat(learning): LearningProfile en_voice/uz_voice fields"
```

---

### Task 3: edge-tts provider + voice catalog

**Files:**
- Modify: `pyproject.toml` (add `edge-tts`), `uv.lock` (regenerate)
- Modify: `apps/common/tts.py`
- Test: `apps/common/tests/test_tts.py` (append)

**Interfaces:**
- Produces:
  - `TTSProvider.synthesize(text: str, lang: str = "en", voice: str | None = None) -> bytes`
  - `EdgeTTSProvider` (subclass)
  - `EN_VOICES: list[tuple[str, str]]`, `UZ_VOICES: list[tuple[str, str]]` (id, label)
  - `voice_label(voice_id: str) -> str`

- [ ] **Step 1: Add dependency**

In `pyproject.toml` `dependencies`, add: `"edge-tts>=6.1",`. Then:

```bash
python -m uv lock
```

- [ ] **Step 2: Write the failing test**

```python
# apps/common/tests/test_tts.py  (append)
from unittest.mock import patch

from apps.common import tts as tts_mod


class _FakeCommunicate:
    last_voice = None

    def __init__(self, text, voice):
        _FakeCommunicate.last_voice = voice
        self._text = text

    async def stream(self):
        yield {"type": "audio", "data": b"AB"}
        yield {"type": "WordBoundary"}
        yield {"type": "audio", "data": b"CD"}


def test_edge_tts_passes_voice_and_joins_audio():
    with patch("edge_tts.Communicate", _FakeCommunicate):
        out = tts_mod.EdgeTTSProvider().synthesize("hello", lang="en", voice="en-US-GuyNeural")
    assert out == b"ABCD"
    assert _FakeCommunicate.last_voice == "en-US-GuyNeural"


def test_edge_tts_defaults_voice_per_lang():
    with patch("edge_tts.Communicate", _FakeCommunicate):
        tts_mod.EdgeTTSProvider().synthesize("salom", lang="uz")
    assert _FakeCommunicate.last_voice == "uz-UZ-MadinaNeural"


def test_gtts_accepts_and_ignores_voice_kwarg():
    with patch("apps.common.tts.gTTS") as g:
        g.return_value.write_to_fp.side_effect = lambda fp: fp.write(b"X")
        out = tts_mod.GTTSProvider().synthesize("hi", lang="en", voice="ignored")
    assert out == b"X"


def test_voice_label_known_and_unknown():
    assert "Madina" in tts_mod.voice_label("uz-UZ-MadinaNeural")
    assert tts_mod.voice_label("nope") == "nope"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m uv run pytest apps/common/tests/test_tts.py -v`
Expected: FAIL (`EdgeTTSProvider`/`voice_label` not defined; `GTTSProvider.synthesize` rejects `voice`).

- [ ] **Step 4: Implement**

```python
# apps/common/tts.py
from __future__ import annotations

import asyncio
from importlib import import_module
from io import BytesIO

from django.conf import settings
from gtts import gTTS

EN_VOICES: list[tuple[str, str]] = [
    ("en-US-AriaNeural", "Aria (ayol)"),
    ("en-US-JennyNeural", "Jenny (ayol)"),
    ("en-US-GuyNeural", "Guy (erkak)"),
    ("en-US-ChristopherNeural", "Christopher (erkak)"),
    ("en-GB-SoniaNeural", "Sonia (UK, ayol)"),
    ("en-GB-RyanNeural", "Ryan (UK, erkak)"),
]
UZ_VOICES: list[tuple[str, str]] = [
    ("uz-UZ-MadinaNeural", "Madina (ayol)"),
    ("uz-UZ-SardorNeural", "Sardor (erkak)"),
]
_DEFAULT_VOICE = {"en": "en-US-AriaNeural", "uz": "uz-UZ-MadinaNeural"}
_LABELS = dict(EN_VOICES + UZ_VOICES)


def voice_label(voice_id: str) -> str:
    return _LABELS.get(voice_id, voice_id)


class TTSProvider:
    """Interface for text-to-speech backends returning MP3 bytes."""

    def synthesize(self, text: str, lang: str = "en", voice: str | None = None) -> bytes:
        raise NotImplementedError


class GTTSProvider(TTSProvider):
    def __init__(self, tld: str = "co.uk", slow: bool = False) -> None:
        self.tld = tld
        self.slow = slow

    def synthesize(self, text: str, lang: str = "en", voice: str | None = None) -> bytes:
        # gTTS has no voice selection — `voice` is accepted for interface parity, ignored.
        fp = BytesIO()
        gTTS(text, lang=lang, slow=self.slow, tld=self.tld).write_to_fp(fp)
        return fp.getvalue()


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge online neural voices (free, no key). Voice-aware."""

    def synthesize(self, text: str, lang: str = "en", voice: str | None = None) -> bytes:
        voice = voice or _DEFAULT_VOICE.get(lang, _DEFAULT_VOICE["en"])
        return asyncio.run(self._synth(text, voice))

    async def _synth(self, text: str, voice: str) -> bytes:
        import edge_tts

        buf = bytearray()
        async for chunk in edge_tts.Communicate(text, voice).stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        if not buf:
            raise RuntimeError("edge-tts returned no audio")
        return bytes(buf)


def get_tts_provider() -> TTSProvider:
    path = getattr(settings, "TTS_PROVIDER", "apps.common.tts.GTTSProvider")
    module_path, _, cls_name = path.rpartition(".")
    return getattr(import_module(module_path), cls_name)()
```

- [ ] **Step 5: Run tests**

Run: `python -m uv run pytest apps/common/tests/test_tts.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock apps/common/tts.py apps/common/tests/test_tts.py
git commit -m "feat(tts): edge-tts multi-voice provider + voice catalog"
```

---

### Task 4: Combined daily audio (EN×repeat → UZ), cached

**Files:**
- Modify: `apps/learning/services/audio.py`
- Test: `apps/learning/tests/test_audio.py` (replace)

**Interfaces:**
- Consumes: `get_tts_provider()`, `GTTSProvider`, `EN_VOICES`/`UZ_VOICES` (Task 3).
- Produces: `build_daily_audio(words: list[Word], en_voice: str, uz_voice: str, repeat: int) -> bytes`; helper `_segment(word, lang, voice, text) -> AudioSegment | None` (per-word single-voice cache at `media/audio/seg/<lang>/<voice>/<word.id>.mp3`).

- [ ] **Step 1: Write the failing test** (mock the audio layer — no ffmpeg needed)

```python
# apps/learning/tests/test_audio.py  (replace file)
from unittest.mock import MagicMock, patch

import pytest

from apps.catalog.models import Book, Unit, Word
from apps.learning.services import audio as audio_mod

pytestmark = pytest.mark.django_db


@pytest.fixture
def words(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    return [
        Word.objects.create(unit=unit, en="afraid", uz="qo'rqib", order=1),
        Word.objects.create(unit=unit, en="brave", uz="jasur", order=2),
    ]


def test_build_daily_audio_synthesizes_en_and_uz_with_voices(words):
    seg = MagicMock(name="AudioSegment")
    seg.__mul__.return_value = seg
    seg.__add__.return_value = seg
    with patch.object(audio_mod, "_segment", return_value=seg) as m, \
         patch.object(audio_mod, "_export", return_value=b"MP3"):
        out = audio_mod.build_daily_audio(words, "en-US-GuyNeural", "uz-UZ-SardorNeural", 3)
    assert out == b"MP3"
    # one EN + one UZ segment per word, with the configured voices
    calls = {(c.args[1], c.args[2]) for c in m.call_args_list}
    assert ("en", "en-US-GuyNeural") in calls
    assert ("uz", "uz-UZ-SardorNeural") in calls
    # EN repeated `repeat` times
    seg.__mul__.assert_any_call(3)


def test_segment_caches_on_disk(words):
    w = words[0]
    with patch.object(audio_mod, "_tts_bytes", return_value=b"MP3") as synth, \
         patch.object(audio_mod, "AudioSegment") as seg_cls:
        seg_cls.from_file.return_value = "SEG"
        first = audio_mod._segment(w, "en", "en-US-AriaNeural", "afraid")
        assert first == "SEG"
        synth.assert_called_once()
        synth.reset_mock()
        second = audio_mod._segment(w, "en", "en-US-AriaNeural", "afraid")
        assert second == "SEG"
        synth.assert_not_called()  # cache hit


def test_tts_bytes_falls_back_to_gtts_for_english(words):
    boom = MagicMock()
    boom.synthesize.side_effect = RuntimeError("edge down")
    with patch.object(audio_mod, "get_tts_provider", return_value=boom), \
         patch("apps.common.tts.GTTSProvider") as g:
        g.return_value.synthesize.return_value = b"GT"
        assert audio_mod._tts_bytes("hi", "en", "en-US-AriaNeural") == b"GT"


def test_tts_bytes_uz_failure_returns_none(words):
    boom = MagicMock()
    boom.synthesize.side_effect = RuntimeError("edge down")
    with patch.object(audio_mod, "get_tts_provider", return_value=boom):
        assert audio_mod._tts_bytes("salom", "uz", "uz-UZ-MadinaNeural") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest apps/learning/tests/test_audio.py -v`
Expected: FAIL (`build_daily_audio`/`_segment`/`_tts_bytes`/`_export` not defined).

- [ ] **Step 3: Implement**

```python
# apps/learning/services/audio.py
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from django.conf import settings
from pydub import AudioSegment

from apps.catalog.models import Word
from apps.common.tts import get_tts_provider

logger = logging.getLogger(__name__)

_GAP_WORD_MS = 700   # silence between two words
_GAP_EN_UZ_MS = 300  # silence between the EN block and its UZ translation


def _seg_path(word: Word, lang: str, voice: str) -> Path:
    return Path(settings.MEDIA_ROOT) / "audio" / "seg" / lang / voice / f"{word.id}.mp3"


def _tts_bytes(text: str, lang: str, voice: str) -> bytes | None:
    """Configured provider; on failure fall back to gTTS for EN, drop UZ."""
    try:
        return get_tts_provider().synthesize(text, lang=lang, voice=voice)
    except Exception as exc:  # noqa: BLE001 — degrade, never crash the delivery
        logger.warning("tts failed lang=%s voice=%s: %s", lang, voice, exc)
        if lang == "en":
            from apps.common.tts import GTTSProvider

            try:
                return GTTSProvider().synthesize(text, lang="en")
            except Exception as exc2:  # noqa: BLE001
                logger.warning("gTTS fallback failed: %s", exc2)
        return None


def _segment(word: Word, lang: str, voice: str, text: str) -> AudioSegment | None:
    path = _seg_path(word, lang, voice)
    if path.exists():
        return AudioSegment.from_file(path)
    data = _tts_bytes(text, lang, voice)
    if data is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return AudioSegment.from_file(BytesIO(data), format="mp3")


def _export(combined: AudioSegment) -> bytes:
    buf = BytesIO()
    combined.export(buf, format="mp3")
    return buf.getvalue()


def build_daily_audio(words: list[Word], en_voice: str, uz_voice: str, repeat: int) -> bytes:
    """One MP3 for the day: per word `EN×repeat` (+300ms) `UZ`, words joined by 700ms."""
    segs: list[AudioSegment] = []
    for word in words:
        en = _segment(word, "en", en_voice, word.en)
        if en is None:
            continue
        piece = en * max(1, repeat)
        uz = _segment(word, "uz", uz_voice, word.uz)
        if uz is not None:
            piece = piece + AudioSegment.silent(duration=_GAP_EN_UZ_MS) + uz
        segs.append(piece)
    if not segs:
        return _export(AudioSegment.silent(duration=100))
    combined = segs[0]
    for piece in segs[1:]:
        combined = combined + AudioSegment.silent(duration=_GAP_WORD_MS) + piece
    return _export(combined)
```

(Note: `build_word_audio`/`_render_combined`/`_combined_path` are removed — Task 5 stops calling them.)

- [ ] **Step 4: Run tests**

Run: `python -m uv run pytest apps/learning/tests/test_audio.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/learning/services/audio.py apps/learning/tests/test_audio.py
git commit -m "feat(learning): build_daily_audio (EN x repeat -> UZ), per-segment voice cache"
```

---

### Task 5: Morning delivery v2 (single message + audio + Batafsil)

**Files:**
- Modify: `apps/learning/services/deliver.py`
- Modify: `bot/sender.py`
- Modify: `apps/learning/tests/test_deliver.py`
- Delete: `apps/learning/services/cards.py` + `apps/learning/tests/test_cards.py` (no longer used)

**Interfaces:**
- Consumes: `build_daily_audio` (Task 4), `LearningProfile.en_voice/uz_voice` (Task 2).
- Produces:
  - `bot.sender.send_daily(chat_id: int, caption: str, audio: bytes | None, webapp_url: str | None) -> None`
  - `deliver._word_list_caption(words) -> str`
  - `deliver.today_session_payload(user_id) -> tuple[str, bytes | None] | None`

- [ ] **Step 1: Write the failing test**

```python
# apps/learning/tests/test_deliver.py  — replace the three render_daily_card patches
# with build_daily_audio + drop image assertions. Full replacement of the module:
from unittest.mock import MagicMock, patch

import pytest
from aiogram.exceptions import TelegramForbiddenError

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
@patch("apps.learning.services.deliver.build_daily_audio", return_value=b"AUD")
def test_run_delivery_sends_one_audio_and_caption(mock_audio, mock_send, user_with_words):
    user, book, unit = user_with_words
    session = deliver_mod.run_delivery(user.id)
    assert session.status == DailySession.Status.DELIVERED
    assert list(session.words.values_list("en", flat=True)) == ["w1", "w2", "w3"]
    assert WordProgress.objects.filter(user=user).count() == 3
    mock_audio.assert_called_once()  # ONE combined audio, not one-per-word
    mock_send.assert_called_once()
    _chat, caption, audio, _webapp = mock_send.call_args.args
    assert audio == b"AUD"
    assert "w1" in caption and "w2" in caption and "w3" in caption  # list caption


@patch("apps.learning.services.deliver.send_daily")
@patch("apps.learning.services.deliver.build_daily_audio", return_value=b"AUD")
def test_run_delivery_idempotent(mock_audio, mock_send, user_with_words):
    user, *_ = user_with_words
    deliver_mod.run_delivery(user.id)
    mock_send.reset_mock()
    assert deliver_mod.run_delivery(user.id) is None
    mock_send.assert_not_called()


@patch("apps.learning.services.deliver.send_daily")
def test_run_delivery_no_content(mock_send, user_with_words):
    user, *_ = user_with_words
    p = user.learning_profile
    p.current_word_order = 5
    p.save()
    assert deliver_mod.run_delivery(user.id) is None
    mock_send.assert_not_called()


@patch("apps.learning.services.deliver.send_daily",
       side_effect=TelegramForbiddenError(method=MagicMock(), message="blocked"))
@patch("apps.learning.services.deliver.build_daily_audio", return_value=b"AUD")
def test_run_delivery_blocked(mock_audio, mock_send, user_with_words):
    user, *_ = user_with_words
    assert deliver_mod.run_delivery(user.id) is None
    user.telegram.refresh_from_db()
    assert user.telegram.blocked_bot is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest apps/learning/tests/test_deliver.py -v`
Expected: FAIL (`build_daily_audio` not imported in deliver; `send_daily` signature mismatch).

- [ ] **Step 3: Implement — `apps/learning/services/deliver.py`**

Replace imports + `_caption` + the delivery body:

```python
from aiogram.exceptions import TelegramForbiddenError
from django.conf import settings as dj_settings
from django.utils import timezone

from apps.learning.models import DailySession, LearningProfile, SessionWord, WordProgress
from apps.learning.services.audio import build_daily_audio
from apps.learning.services.delivery import advance_position, next_words
from bot.sender import send_daily


def _local_date(profile):
    from zoneinfo import ZoneInfo
    return timezone.now().astimezone(ZoneInfo(profile.timezone)).date()


def _word_list_caption(words) -> str:
    lines = ["📅 <b>Bugungi so'zlar</b>", ""]
    for i, w in enumerate(words, 1):
        ipa = f" <i>{w.pronunciation}</i>" if w.pronunciation else ""
        lines.append(f"{i}. <b>{w.en}</b>{ipa} — {w.uz}")
    lines.append("")
    lines.append("🔊 Audio: inglizcha talaffuz + o'zbekcha tarjima")
    return "\n".join(lines)


def _webapp_today_url() -> str | None:
    base = dj_settings.WEBAPP_URL
    if not base:
        return None
    return f"{base}{'&' if '?' in base else '?'}view=today"
```

Rewrite `run_delivery` so the payload build replaces the per-word items loop:

```python
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
    session, _ = DailySession.objects.get_or_create(
        user_id=user_id, date=date,
        defaults={"book": profile.current_book, "unit": profile.current_unit},
    )
    if session.status == DailySession.Status.DELIVERED:
        return None

    words = next_words(profile, profile.words_per_session)
    if not words:
        return None

    for order, word in enumerate(words, start=1):
        SessionWord.objects.get_or_create(daily_session=session, word=word, defaults={"order": order})
        WordProgress.objects.get_or_create(user_id=user_id, word=word)

    audio = (
        build_daily_audio(words, profile.en_voice, profile.uz_voice, profile.audio_repeat)
        if profile.audio_enabled else None
    )
    try:
        send_daily(account.telegram_id, _word_list_caption(words), audio, _webapp_today_url())
    except TelegramForbiddenError:
        account.blocked_bot = True
        account.save(update_fields=["blocked_bot", "updated_at"])
        return None

    advance_position(profile, words[-1])
    session.status = DailySession.Status.DELIVERED
    session.delivered_at = timezone.now()
    session.save(update_fields=["status", "delivered_at", "updated_at"])
    return session
```

Replace `today_session_items` with:

```python
def today_session_payload(user_id: int):
    """Rebuild today's (caption, audio) so 'Bugungi vazifa' can re-send it."""
    profile, session = _today_session(user_id)
    if session is None:
        return None
    words = [sw.word for sw in session.session_words.select_related("word__unit__book").order_by("order")]
    if not words:
        return None
    audio = (
        build_daily_audio(words, profile.en_voice, profile.uz_voice, profile.audio_repeat)
        if profile.audio_enabled else None
    )
    return _word_list_caption(words), audio
```

(Keep `today_session_words`. Update `bot/handlers/daily.py` — the "Bugungi vazifa" handler — to call `today_session_payload` and `send_daily(chat_id, caption, audio, _webapp_today_url())`; adjust its test accordingly.)

- [ ] **Step 4: Implement — `bot/sender.py`** (replace `_send_daily`/`send_daily`)

```python
from aiogram.types import (
    BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo,
)


async def _send_daily(bot, chat_id, caption, audio, webapp_url):
    markup = None
    if webapp_url:
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📖 Batafsil", web_app=WebAppInfo(url=webapp_url))
        ]])
    if audio is None:
        await bot.send_message(chat_id, caption, reply_markup=markup)
        return
    if len(caption) > 1024:
        await bot.send_message(chat_id, caption)
        await bot.send_audio(
            chat_id, BufferedInputFile(audio, "words.mp3"),
            caption="🔊 Bugungi so'zlar", reply_markup=markup,
        )
    else:
        await bot.send_audio(
            chat_id, BufferedInputFile(audio, "words.mp3"),
            caption=caption, reply_markup=markup,
        )


def send_daily(chat_id: int, caption: str, audio: bytes | None, webapp_url: str | None = None) -> None:
    async def _run():
        bot = _make_bot()
        try:
            await _send_daily(bot, chat_id, caption, audio, webapp_url)
        finally:
            await bot.session.close()
    asyncio.run(_run())
```

- [ ] **Step 5: Delete dead card renderer**

```bash
git rm apps/learning/services/cards.py apps/learning/tests/test_cards.py
```

- [ ] **Step 6: Run tests**

Run: `python -m uv run pytest apps/learning/tests/test_deliver.py bot/tests -v`
Expected: PASS (deliver tests + bot daily handler test updated).

- [ ] **Step 7: Commit**

```bash
git add apps/learning/services/deliver.py bot/sender.py apps/learning/tests/test_deliver.py bot/handlers/daily.py bot/tests
git commit -m "feat(learning): morning delivery v2 — one message + one audio + Batafsil"
```

---

### Task 6: Bot settings redesign + voice/repeat pickers

**Files:**
- Modify: `bot/keyboards/settings.py`, `bot/handlers/settings.py`, `bot/strings.py`
- Test: `bot/tests/test_handlers_settings.py` (create or extend)

**Interfaces:**
- Consumes: `EN_VOICES`, `UZ_VOICES`, `voice_label` (Task 3); `LearningProfile.en_voice/uz_voice` (Task 2).
- Produces: `settings_keyboard(profile) -> InlineKeyboardMarkup`; callbacks `set:envoice`, `set:uzvoice`, `set:repeat`, `envoice:<id>`, `uzvoice:<id>`, `repeat:<n>`.

- [ ] **Step 1: Write the failing test**

```python
# bot/tests/test_handlers_settings.py
import pytest
from apps.accounts.models import User
from apps.learning.models import LearningProfile
from bot.keyboards.settings import en_voice_keyboard, settings_keyboard
from apps.common.tts import EN_VOICES


@pytest.mark.django_db
def test_settings_keyboard_shows_current_values():
    p = LearningProfile(user=User(first_name="x"), words_per_session=7, audio_repeat=3)
    texts = [b.text for row in settings_keyboard(p).inline_keyboard for b in row]
    assert any("7" in t for t in texts)          # words per session shown
    assert any("Aria" in t for t in texts)       # default EN voice label shown
    assert any("Madina" in t for t in texts)     # default UZ voice label shown


def test_en_voice_keyboard_lists_all_en_voices():
    cbs = [b.callback_data for row in en_voice_keyboard().inline_keyboard for b in row]
    for vid, _ in EN_VOICES:
        assert f"envoice:{vid}" in cbs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest bot/tests/test_handlers_settings.py -v`
Expected: FAIL (`en_voice_keyboard` missing; `settings_keyboard` takes no arg).

- [ ] **Step 3: Implement keyboards — `bot/keyboards/settings.py`**

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from apps.common.tts import EN_VOICES, UZ_VOICES, voice_label
from bot import strings


def settings_keyboard(profile) -> InlineKeyboardMarkup:
    audio = strings.BTN_AUDIO_ON if profile.audio_enabled else strings.BTN_AUDIO_OFF
    nudges = strings.BTN_NUDGES_ON if profile.nudges_enabled else strings.BTN_NUDGES_OFF
    days = ", ".join(strings.WEEKDAY_SHORT[d] for d in profile.study_weekdays)
    rows = [
        [InlineKeyboardButton(text=f"🔤 {strings.SETTINGS_WORDS}: {profile.words_per_session}",
                              callback_data="set:words")],
        [InlineKeyboardButton(text=f"📅 {strings.SETTINGS_DAYS}: {days}", callback_data="set:days")],
        [InlineKeyboardButton(text=f"🌅 {strings.SETTINGS_MORNING}: {profile.morning_time:%H:%M}",
                              callback_data="set:morning"),
         InlineKeyboardButton(text=f"🎯 {strings.SETTINGS_EXAM}: {profile.exam_time:%H:%M}",
                              callback_data="set:exam")],
        [InlineKeyboardButton(text=f"🔊 {strings.SETTINGS_AUDIO}: {audio}", callback_data="set:audio")],
        [InlineKeyboardButton(text=f"🇬🇧 {strings.SETTINGS_EN_VOICE}: {voice_label(profile.en_voice)}",
                              callback_data="set:envoice")],
        [InlineKeyboardButton(text=f"🇺🇿 {strings.SETTINGS_UZ_VOICE}: {voice_label(profile.uz_voice)}",
                              callback_data="set:uzvoice")],
        [InlineKeyboardButton(text=f"🔁 {strings.SETTINGS_REPEAT}: {profile.audio_repeat}",
                              callback_data="set:repeat")],
        [InlineKeyboardButton(text=f"🔔 {strings.SETTINGS_NUDGES}: {nudges}", callback_data="set:nudges")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _voice_keyboard(voices, prefix, current) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=("✅ " if vid == current else "") + label, callback_data=f"{prefix}:{vid}"
    )] for vid, label in voices]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def en_voice_keyboard(current: str = "") -> InlineKeyboardMarkup:
    return _voice_keyboard(EN_VOICES, "envoice", current)


def uz_voice_keyboard(current: str = "") -> InlineKeyboardMarkup:
    return _voice_keyboard(UZ_VOICES, "uzvoice", current)


def repeat_keyboard(current: int = 0) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=("✅ " if n == current else "") + str(n), callback_data=f"repeat:{n}"
    ) for n in (1, 2, 3)]]
    return InlineKeyboardMarkup(inline_keyboard=rows)
```

- [ ] **Step 4: Add strings — `bot/strings.py`**

```python
SETTINGS_EN_VOICE = "Ingliz ovozi"
SETTINGS_UZ_VOICE = "O'zbek ovozi"
SETTINGS_REPEAT = "Takror"
```

- [ ] **Step 5: Implement handlers — `bot/handlers/settings.py`**

Change `cmd_settings` and `format_profile`/`toggle_nudges` to pass `profile` to `settings_keyboard(profile)`, add `en_voice`/`uz_voice`/`audio_repeat` lines to `format_profile`, and add:

```python
from asgiref.sync import sync_to_async
from bot.keyboards.settings import (
    en_voice_keyboard, repeat_keyboard, settings_keyboard, uz_voice_keyboard,
)


@router.callback_query(F.data == "set:envoice")
async def edit_en_voice(callback, profile):
    await callback.answer()
    await callback.message.edit_text(strings.SETTINGS_EN_VOICE,
                                     reply_markup=en_voice_keyboard(profile.en_voice))


@router.callback_query(F.data.startswith("envoice:"))
async def save_en_voice(callback, profile):
    await callback.answer()
    profile.en_voice = callback.data.split(":", 1)[1]
    await sync_to_async(profile.save)(update_fields=["en_voice", "updated_at"])
    await callback.message.edit_text(format_profile(profile), reply_markup=settings_keyboard(profile))
```

Repeat the same pattern for `set:uzvoice`/`uzvoice:` (field `uz_voice`, `uz_voice_keyboard`) and `set:repeat`/`repeat:` (field `audio_repeat`, cast `int`, `repeat_keyboard`). Update every `settings_keyboard()` call site to `settings_keyboard(profile)`.

- [ ] **Step 6: Run tests**

Run: `python -m uv run pytest bot/tests/test_handlers_settings.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add bot/keyboards/settings.py bot/handlers/settings.py bot/strings.py bot/tests/test_handlers_settings.py
git commit -m "feat(bot): settings show values + EN/UZ voice + repeat pickers"
```

---

### Task 7: Mini App — voice settings + today deep-link

**Files:**
- Modify: `apps/catalog/views.py` (`_profile_payload`, `_clean_settings`)
- Modify: `templates/webapp/index.html` (settings render + init deep-link)
- Test: `apps/catalog/tests/test_webapp_profile.py` (extend)

**Interfaces:**
- Consumes: `EN_VOICES`, `UZ_VOICES` (Task 3), `LearningProfile.en_voice/uz_voice` (Task 2).
- Produces: profile payload gains `en_voice`, `uz_voice`, `en_voices`, `uz_voices`; `_clean_settings` validates voice ids.

- [ ] **Step 1: Write the failing test**

```python
# apps/catalog/tests/test_webapp_profile.py  (append; reuse the file's signed-initData helper)
def test_profile_returns_voices_and_updates(client, signed_headers, profile_user):
    # GET exposes current voices + the available catalogs
    r = client.get("/webapp/api/profile/", **signed_headers)
    body = r.json()
    assert body["en_voice"] == "en-US-AriaNeural"
    assert any(v[0] == "uz-UZ-SardorNeural" for v in body["uz_voices"])
    # POST a valid voice sticks; an invalid one is dropped
    r = client.post("/webapp/api/profile/", data={"en_voice": "en-US-GuyNeural", "uz_voice": "bogus"},
                    content_type="application/json", **signed_headers)
    assert r.json()["en_voice"] == "en-US-GuyNeural"
    assert r.json()["uz_voice"] == "uz-UZ-MadinaNeural"  # unchanged (bogus rejected)
```

(Match the existing helpers/fixtures already in `test_webapp_profile.py` for building signed initData; adapt names as needed.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m uv run pytest apps/catalog/tests/test_webapp_profile.py -v`
Expected: FAIL (no `en_voice`/`uz_voices` in payload).

- [ ] **Step 3: Implement backend — `apps/catalog/views.py`**

Add to `_profile_payload` return dict:

```python
        "en_voice": profile.en_voice,
        "uz_voice": profile.uz_voice,
        "en_voices": EN_VOICES,
        "uz_voices": UZ_VOICES,
```

Import at top: `from apps.common.tts import EN_VOICES, UZ_VOICES`. In `_clean_settings`, before `return updates`:

```python
    _EN_IDS = {v[0] for v in EN_VOICES}
    _UZ_IDS = {v[0] for v in UZ_VOICES}
    if payload.get("en_voice") in _EN_IDS:
        updates["en_voice"] = payload["en_voice"]
    if payload.get("uz_voice") in _UZ_IDS:
        updates["uz_voice"] = payload["uz_voice"]
```

- [ ] **Step 4: Implement frontend — `templates/webapp/index.html`**

In the Profil settings render (around lines 471–528, where the day-chips/time/audio controls are built), add two `<select>`s populated from `data.en_voices`/`data.uz_voices`, defaulting to `data.en_voice`/`data.uz_voice`; include `en_voice`/`uz_voice` in the settings save `apiProfile("POST", {...})` body. Use existing classes (no CSS rebuild). Example select:

```html
<select id="s-envoice" class="w-full rounded-xl bg-card border border-line px-3 py-2 text-sm">
  <!-- options injected: data.en_voices.map(([id,label]) => `<option value="${id}" ${id===data.en_voice?'selected':''}>${label}</option>`) -->
</select>
```

In init (line 804), before defaulting to books, honor the deep-link:

```javascript
    const _view = new URLSearchParams(location.search).get("view");
    loadLearned(() => setTab(_view === "today" ? "today" : "books"));
```

- [ ] **Step 5: Verify (curl, no browser needed)**

```bash
python -m uv run pytest apps/catalog/tests/test_webapp_profile.py -v
```
Expected: PASS. (Live check after deploy: open `https://english.omadli.uz/webapp/?view=today` → today tab.)

- [ ] **Step 6: Commit**

```bash
git add apps/catalog/views.py templates/webapp/index.html apps/catalog/tests/test_webapp_profile.py
git commit -m "feat(webapp): voice settings + ?view=today deep-link into today tab"
```

---

### Task 8: Integration — full suite, prod config, deploy

**Files:**
- Modify: none (verification + deploy)

- [ ] **Step 1: Full test suite + lint**

Run: `docker compose up -d db && python -m uv run pytest && python -m uv run ruff check .`
Expected: ALL green, ruff clean. Fix any regressions (esp. callers of the removed `build_word_audio`/`render_daily_card`/`today_session_items`).

- [ ] **Step 2: Grep for stale references**

Run: `python -m uv run ruff check . && grep -rn "build_word_audio\|render_daily_card\|today_session_items" apps bot`
Expected: no matches outside history.

- [ ] **Step 3: Merge to main (triggers prod deploy)**

```bash
git checkout main && git merge --no-ff daily-words-v2 && git push origin main
```

- [ ] **Step 4: Point prod at edge-tts**

On the server, add to `/home/ubuntu/english_quiz/.env`:
```
TTS_PROVIDER=apps.common.tts.EdgeTTSProvider
```
Then `docker compose -f compose.yaml -f compose.prod.yaml up -d worker beat bot web` (recreate to pick up the env). CI already rebuilt the image with `edge-tts`.

- [ ] **Step 5: Live verify**

- `https://english.omadli.uz/webapp/?view=today` opens the today tab.
- Bot: trigger a delivery for a test user (or wait for the morning slot) → one message: word list + one audio (EN×repeat → UZ) + 📖 Batafsil.
- Settings → voice pickers change EN/UZ voice; next audio uses the new voice.

---

## Notes / carryover

- edge-tts is network-bound in the Celery worker; per-segment cache absorbs repeat cost; gTTS fallback covers outages.
- Uzbek has only 2 edge-tts voices — the "other girls' voices" the user mentioned apply to English only.
- Sub-projects ② (guardian management) and ③ (dashboards/reports) are separate specs.
