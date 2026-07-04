import pytest

from apps.accounts.models import User
from apps.catalog.models import Book, Unit
from apps.quiz.models import GroupQuizSession
from apps.quiz.services.session import (
    get_active_session,
    set_book,
    start_configuring,
    toggle_unit,
    units_for_book,
)

pytestmark = pytest.mark.django_db


def _user_id() -> int:
    # started_by is a real FK to the local User table (DEFERRABLE INITIALLY
    # DEFERRED on Postgres), so a bare literal like 5 violates it at teardown
    # even though the INSERT itself appears to succeed mid-test.
    return User.objects.create(first_name="Admin").id


def test_start_configuring_creates_one_active():
    user_id = _user_id()
    s = start_configuring(-100, user_id)
    assert s is not None
    assert s.status == GroupQuizSession.Status.CONFIGURING
    # a second start while active returns None
    assert start_configuring(-100, user_id) is None


def test_get_active_session():
    assert get_active_session(-100) is None
    s = start_configuring(-100, _user_id())
    assert get_active_session(-100).id == s.id


def test_set_book_and_toggle_unit():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    u1 = Unit.objects.create(book=book, number=1)
    u2 = Unit.objects.create(book=book, number=2)
    s = start_configuring(-100, _user_id())
    set_book(s, 1)
    s.refresh_from_db()
    assert s.book_id == book.id
    toggle_unit(s, u1.id)
    toggle_unit(s, u2.id)
    toggle_unit(s, u1.id)  # off again
    s.refresh_from_db()
    assert s.unit_ids == [u2.id]
    assert [u.id for u in units_for_book(1)] == [u1.id, u2.id]
