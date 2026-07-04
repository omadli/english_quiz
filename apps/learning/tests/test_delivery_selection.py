import pytest

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import LearningProfile
from apps.learning.services.delivery import advance_position, next_words

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_units():
    b = Book.objects.create(number=1, title="B1", slug="b1")
    u1 = Unit.objects.create(book=b, number=1)
    u2 = Unit.objects.create(book=b, number=2)
    for i in range(1, 4):
        Word.objects.create(unit=u1, en=f"u1w{i}", uz=f"a{i}", order=i)
    for i in range(1, 4):
        Word.objects.create(unit=u2, en=f"u2w{i}", uz=f"b{i}", order=i)
    return b, u1, u2


def _profile(book, unit, order):
    u = User.objects.create(first_name="T")
    return LearningProfile.objects.create(
        user=u, current_book=book, current_unit=unit, current_word_order=order
    )


def test_next_words_from_start_of_unit(two_units):
    b, u1, u2 = two_units
    p = _profile(b, u1, 0)  # nothing delivered yet in unit 1
    words = next_words(p, 2)
    assert [w.en for w in words] == ["u1w1", "u1w2"]


def test_next_words_crosses_unit_boundary(two_units):
    b, u1, u2 = two_units
    p = _profile(b, u1, 2)  # last delivered = u1w2
    words = next_words(p, 2)
    assert [w.en for w in words] == ["u1w3", "u2w1"]


def test_next_words_empty_at_end(two_units):
    b, u1, u2 = two_units
    p = _profile(b, u2, 3)  # last word delivered
    assert next_words(p, 2) == []


def test_advance_position_sets_to_word(two_units):
    b, u1, u2 = two_units
    p = _profile(b, u1, 0)
    w = Word.objects.get(en="u2w1")
    advance_position(p, w)
    p.refresh_from_db()
    assert p.current_unit_id == u2.id
    assert p.current_word_order == 1
