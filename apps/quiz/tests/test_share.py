import pytest

from apps.catalog.models import Book
from apps.quiz.models import GroupQuizSession, SharedQuiz
from apps.quiz.services.session import create_group_session_from_shared
from apps.quiz.services.share import (
    get_shared_quiz,
    recent_shared_quizzes,
    save_shared_quiz,
)

pytestmark = pytest.mark.django_db


def test_save_shared_quiz_persists_config():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    quiz = save_shared_quiz(555, book.id, [10, 11], 15, 20, ["en_uz"])
    assert quiz.pk is not None
    assert quiz.unit_ids == [10, 11]
    assert quiz.question_count == 15
    assert quiz.interval_seconds == 20
    assert quiz.question_types == ["en_uz"]


def test_get_shared_quiz_by_token():
    quiz = save_shared_quiz(555, None, [10], 10, 30, None)
    assert get_shared_quiz(str(quiz.pk)) == quiz


def test_get_shared_quiz_bad_token_returns_none():
    assert get_shared_quiz("abc") is None       # not digits → no crash
    assert get_shared_quiz("999999") is None     # unknown id


def test_recent_shared_quizzes_returns_cards_for_owner_only():
    book = Book.objects.create(number=2, title="B2", slug="b2")
    save_shared_quiz(555, book.id, [1, 2, 3], 20, 30, ["en_uz"])
    save_shared_quiz(999, book.id, [1], 10, 30, None)  # a different user's quiz
    cards = recent_shared_quizzes(555)
    assert len(cards) == 1
    assert cards[0]["title"] == "🧠 B2 — 20 savol"
    assert cards[0]["desc"] == "3 bo'lim · 30s"


def test_get_shared_quiz_empty_token_returns_none():
    SharedQuiz.objects.create(created_by_telegram_id=1)
    assert get_shared_quiz("") is None


def test_create_group_session_from_shared_copies_config():
    book = Book.objects.create(number=3, title="B3", slug="b3")
    shared = save_shared_quiz(555, book.id, [1, 2], 25, 45, ["uz_en"])
    session = create_group_session_from_shared(-100, 555, shared)
    assert session.chat_id == -100
    assert session.started_by_telegram_id == 555
    assert session.book_id == book.id
    assert session.unit_ids == [1, 2]
    assert session.question_count == 25
    assert session.interval_seconds == 45
    assert session.question_types == ["uz_en"]
    assert session.status == GroupQuizSession.Status.CONFIGURING


def test_create_group_session_from_shared_blocks_when_active():
    shared = save_shared_quiz(555, None, [1], 10, 30, None)
    assert create_group_session_from_shared(-100, 555, shared) is not None
    # a quiz already active in this chat → refuse a second one
    assert create_group_session_from_shared(-100, 555, shared) is None
