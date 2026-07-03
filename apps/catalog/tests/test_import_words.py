import json

import pytest
from django.core.management import call_command

from apps.catalog.models import Book, Unit, Word

pytestmark = pytest.mark.django_db

SAMPLE = [
    {
        "model": "words.word",
        "pk": 1,
        "fields": {
            "book": 1, "unit": 1, "en": "afraid", "uz": "qo'rqib",
            "definition": "feels fear", "example": "was <strong>afraid</strong>",
            "pronunciation": "[əˈfreid] adj.", "image": "images/words/1/1/afraid.jpg",
        },
    },
    {
        "model": "words.word",
        "pk": 2,
        "fields": {
            "book": 1, "unit": 1, "en": "agree", "uz": "rozi",
            "definition": "say yes", "example": "I <strong>agree</strong>",
            "pronunciation": "[əˈɡriː] v.", "image": "images/words/1/1/agree.jpg",
        },
    },
]


@pytest.fixture
def data_dir(tmp_path):
    (tmp_path / "book1.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    return tmp_path


def test_import_creates_book_unit_words(data_dir):
    call_command("import_words", "--book", "1", "--data-dir", str(data_dir))
    book = Book.objects.get(number=1)
    assert book.title == "4000 Essential English Words 1"
    assert book.word_count == 2
    unit = Unit.objects.get(book=book, number=1)
    assert unit.word_count == 2
    word = Word.objects.get(en="afraid")
    assert word.uz == "qo'rqib"
    assert word.pronunciation == "[əˈfreid]"
    assert word.part_of_speech == "adj."
    assert word.order == 1


def test_import_is_idempotent(data_dir):
    call_command("import_words", "--book", "1", "--data-dir", str(data_dir))
    call_command("import_words", "--book", "1", "--data-dir", str(data_dir))
    assert Word.objects.filter(en="afraid").count() == 1
    assert Book.objects.get(number=1).word_count == 2


def test_dry_run_writes_nothing(data_dir):
    call_command("import_words", "--book", "1", "--data-dir", str(data_dir), "--dry-run")
    assert Book.objects.count() == 0
