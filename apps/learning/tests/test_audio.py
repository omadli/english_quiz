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
