import pytest
from django.db import IntegrityError

from apps.catalog.models import Book, Unit, Word, parse_pronunciation

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("[əˈfreid] adj.", ("[əˈfreid]", "adj.")),
        ("[əˈɡriː] v.", ("[əˈɡriː]", "v.")),
        ("n.", ("", "n.")),
        ("", ("", "")),
        (None, ("", "")),
    ],
)
def test_parse_pronunciation(raw, expected):
    assert parse_pronunciation(raw) == expected


def test_word_book_property_and_str():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="qo'rqib", order=1)
    assert word.book == book
    assert str(word) == "afraid — qo'rqib"


def test_unit_unique_per_book():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    Unit.objects.create(book=book, number=1)
    with pytest.raises(IntegrityError):
        Unit.objects.create(book=book, number=1)


def test_word_unique_per_unit():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    unit = Unit.objects.create(book=book, number=1)
    Word.objects.create(unit=unit, en="afraid", uz="a")
    with pytest.raises(IntegrityError):
        Word.objects.create(unit=unit, en="afraid", uz="b")
