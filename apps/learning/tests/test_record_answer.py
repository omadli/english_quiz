import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, ExamQuestion, WordProgress
from apps.learning.services.exam_grade import record_answer

pytestmark = pytest.mark.django_db


def _question(correct_option=1):
    user = User.objects.create(first_name="T")
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    session = DailySession.objects.create(
        user=user, date=timezone.now().date(), status=DailySession.Status.EXAM_SENT,
        total=1, score=0,
    )
    q = ExamQuestion.objects.create(
        daily_session=session, word=word, question_type=ExamQuestion.QType.EN_UZ,
        poll_id="poll-1", options=["a", "b", "c", "d"], correct_option=correct_option,
    )
    return user, word, session, q


def test_record_correct_answer_updates_all():
    user, word, session, q = _question(correct_option=1)
    record_answer("poll-1", [1])  # chose correct
    q.refresh_from_db()
    session.refresh_from_db()
    assert q.chosen_option == 1
    assert q.is_correct is True
    assert q.answered_at is not None
    assert session.score == 1
    assert WordProgress.objects.get(user=user, word=word).repetitions == 1


def test_record_wrong_answer_does_not_increment_score():
    user, word, session, q = _question(correct_option=1)
    record_answer("poll-1", [3])  # wrong
    q.refresh_from_db()
    session.refresh_from_db()
    assert q.is_correct is False
    assert session.score == 0
    assert WordProgress.objects.get(user=user, word=word).wrong_count == 1


def test_record_answer_idempotent_and_ignores_unknown():
    user, word, session, q = _question(correct_option=1)
    record_answer("poll-1", [1])
    record_answer("poll-1", [3])   # already answered → ignored
    session.refresh_from_db()
    assert session.score == 1      # not double-counted
    record_answer("unknown-poll", [0])  # no crash
