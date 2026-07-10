import pytest

from apps.catalog.models import Book
from apps.quiz.models import GroupQuizSession
from apps.quiz.services.session import create_group_session_from_config
from apps.quiz.services.share import save_shared_quiz

pytestmark = pytest.mark.django_db


def test_save_shared_quiz_persists_config():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    quiz = save_shared_quiz(555, book.id, [10, 11], 15, 20, ["en_uz"])
    assert quiz.pk is not None
    assert quiz.unit_ids == [10, 11]
    assert quiz.question_count == 15
    assert quiz.interval_seconds == 20
    assert quiz.question_types == ["en_uz"]


def _cfg(book_id, unit_ids, count, interval, types):
    return {"book_id": book_id, "unit_ids": unit_ids, "count": count,
            "interval": interval, "types": types}


def test_create_group_session_from_config_copies_config():
    book = Book.objects.create(number=3, title="B3", slug="b3")
    session = create_group_session_from_config(
        -100, 555, _cfg(book.id, [1, 2], 25, 45, ["uz_en"])
    )
    assert session.chat_id == -100
    assert session.started_by_telegram_id == 555
    assert session.book_id == book.id
    assert session.unit_ids == [1, 2]
    assert session.question_count == 25
    assert session.interval_seconds == 45
    assert session.question_types == ["uz_en"]
    assert session.status == GroupQuizSession.Status.CONFIGURING


def test_create_group_session_from_config_blocks_when_active():
    cfg = _cfg(None, [1], 10, 30, [])
    assert create_group_session_from_config(-100, 555, cfg) is not None
    # a quiz already active in this chat → refuse a second one
    assert create_group_session_from_config(-100, 555, cfg) is None
