import pytest
from django.db import IntegrityError

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, SessionWord, WordProgress

pytestmark = pytest.mark.django_db


def _user():
    return User.objects.create(first_name="T")


def _word():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    return Word.objects.create(unit=unit, en="afraid", uz="a", order=1)


def test_daily_session_unique_per_user_date():
    u = _user()
    DailySession.objects.create(user=u, date="2026-07-03")
    with pytest.raises(IntegrityError):
        DailySession.objects.create(user=u, date="2026-07-03")


def test_session_words_through_order():
    u = _user()
    w = _word()
    ds = DailySession.objects.create(user=u, date="2026-07-03")
    SessionWord.objects.create(daily_session=ds, word=w, order=1)
    assert list(ds.words.all()) == [w]


def test_word_progress_defaults_and_unique():
    u = _user()
    w = _word()
    wp = WordProgress.objects.create(user=u, word=w)
    assert wp.status == "new"
    assert wp.ease_factor == 2.5
    assert wp.repetitions == 0
    assert wp.interval_days == 0
    with pytest.raises(IntegrityError):
        WordProgress.objects.create(user=u, word=w)
