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
