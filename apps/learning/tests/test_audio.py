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
    calls = {(c.args[1], c.args[2]) for c in m.call_args_list}
    assert ("en", "en-US-GuyNeural") in calls
    assert ("uz", "uz-UZ-SardorNeural") in calls
    seg.__mul__.assert_any_call(3)  # EN repeated `repeat` times


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
