import pytest

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


def test_start_configuring_creates_one_active():
    s = start_configuring(-100, 999555)
    assert s is not None
    assert s.status == GroupQuizSession.Status.CONFIGURING
    assert s.started_by_telegram_id == 999555
    # a second start while active returns None
    assert start_configuring(-100, 999555) is None


def test_get_active_session():
    assert get_active_session(-100) is None
    s = start_configuring(-100, 999555)
    assert get_active_session(-100).id == s.id


def test_set_book_and_toggle_unit():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    u1 = Unit.objects.create(book=book, number=1)
    u2 = Unit.objects.create(book=book, number=2)
    s = start_configuring(-100, 999555)
    set_book(s, 1)
    s.refresh_from_db()
    assert s.book_id == book.id
    toggle_unit(s, u1.id)
    toggle_unit(s, u2.id)
    toggle_unit(s, u1.id)  # off again
    s.refresh_from_db()
    assert s.unit_ids == [u2.id]
    assert [u.id for u in units_for_book(1)] == [u1.id, u2.id]


def test_type_count_interval_and_abort():
    from apps.quiz.services.session import abort_active, set_count, set_interval, toggle_type

    s = start_configuring(-200, 5)
    toggle_type(s, "en_uz")
    toggle_type(s, "uz_en")
    toggle_type(s, "en_uz")  # off
    s.refresh_from_db()
    assert s.question_types == ["uz_en"]
    set_count(s, 15)
    set_interval(s, 30)
    s.refresh_from_db()
    assert s.question_count == 15
    assert s.interval_seconds == 30
    assert abort_active(-200) is True
    s.refresh_from_db()
    assert s.status == GroupQuizSession.Status.ABORTED
    assert abort_active(-200) is False  # nothing active now
