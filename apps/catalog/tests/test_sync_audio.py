from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.catalog.models import Book, Unit, Word

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    # Django's FileField writes hit the real filesystem and are NOT rolled back
    # by the test-DB transaction, so reusing MEDIA_ROOT across runs makes
    # get_available_name() append a random suffix to "afraid.mp3" once a
    # same-named file already exists on disk from a prior run. Isolate each
    # test run under a throwaway MEDIA_ROOT so filenames stay deterministic.
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def word():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    unit = Unit.objects.create(book=book, number=1)
    return Word.objects.create(unit=unit, en="afraid", uz="a", order=1)


@patch("apps.catalog.management.commands.sync_audio.get_tts_provider")
def test_gtts_source_sets_audio(mock_get_provider, word):
    mock_get_provider.return_value.synthesize.return_value = b"ID3-audio"
    call_command("sync_audio", "--book", "1", "--source", "gtts")
    word.refresh_from_db()
    assert word.audio_en.name.endswith("afraid.mp3")
    assert word.audio_en.read() == b"ID3-audio"


@patch("apps.catalog.management.commands.sync_audio.get_tts_provider")
def test_skips_existing_without_overwrite(mock_get_provider, word):
    mock_get_provider.return_value.synthesize.return_value = b"one"
    call_command("sync_audio", "--book", "1", "--source", "gtts")
    mock_get_provider.return_value.synthesize.return_value = b"two"
    call_command("sync_audio", "--book", "1", "--source", "gtts")
    word.refresh_from_db()
    assert word.audio_en.read() == b"one"
