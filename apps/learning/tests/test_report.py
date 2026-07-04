import pytest
from django.utils import timezone

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, ExamQuestion
from apps.learning.services import report as report_mod

pytestmark = pytest.mark.django_db


def _session_with_answers():
    user = User.objects.create(first_name="T")
    TelegramAccount.objects.create(user=user, telegram_id=555)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    w1 = Word.objects.create(unit=unit, en="right", uz="a", order=1)
    w2 = Word.objects.create(unit=unit, en="wrong", uz="b", order=2)
    session = DailySession.objects.create(
        user=user, date=timezone.now().date(), status=DailySession.Status.EXAM_SENT, total=2,
    )
    ExamQuestion.objects.create(daily_session=session, word=w1, question_type="en_uz",
                                poll_id="p1", options=["a"], correct_option=0, is_correct=True)
    ExamQuestion.objects.create(daily_session=session, word=w2, question_type="en_uz",
                                poll_id="p2", options=["a"], correct_option=0, is_correct=False)
    return user, session


def test_build_report_shows_score_and_wrong_words():
    _, session = _session_with_answers()
    text = report_mod.build_report(session)
    assert "1/2" in text
    assert "wrong" in text  # the wrongly-answered word is listed for review


def test_finalize_exam_marks_completed_and_sends():
    from unittest.mock import patch
    user, session = _session_with_answers()
    with patch("apps.learning.services.report.send_daily") as mock_send:
        report_mod.finalize_exam(session)
    session.refresh_from_db()
    assert session.status == DailySession.Status.COMPLETED
    assert session.score == 1                 # recomputed from is_correct=True count
    assert session.completed_at is not None
    mock_send.assert_called_once()
