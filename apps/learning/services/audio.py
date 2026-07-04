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
        audio_bytes = provider.synthesize(word.uz, lang="uz")
        return AudioSegment.from_file(BytesIO(audio_bytes), format="mp3")
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
