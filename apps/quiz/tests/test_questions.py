import pytest

from apps.catalog.models import Book, Unit, Word
from apps.quiz.services.questions import sample_words

pytestmark = pytest.mark.django_db


def test_sample_words_only_from_given_units():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    u1 = Unit.objects.create(book=book, number=1)
    u2 = Unit.objects.create(book=book, number=2)
    for i in range(5):
        Word.objects.create(unit=u1, en=f"a{i}", uz=f"x{i}", order=i)
    Word.objects.create(unit=u2, en="other", uz="y", order=1)

    words = sample_words([u1.id], 3)
    assert len(words) == 3
    assert all(w.unit_id == u1.id for w in words)


def test_sample_words_caps_at_available():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    u1 = Unit.objects.create(book=book, number=1)
    for i in range(2):
        Word.objects.create(unit=u1, en=f"a{i}", uz=f"x{i}", order=i)
    assert len(sample_words([u1.id], 10)) == 2
