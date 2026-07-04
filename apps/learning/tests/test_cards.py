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
