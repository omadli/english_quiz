from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, ExamQuestion, LearningProfile, SessionWord
from apps.learning.services import exam_deliver

pytestmark = pytest.mark.django_db


@pytest.fixture
def delivered_session():
    user = User.objects.create(first_name="T")
    TelegramAccount.objects.create(user=user, telegram_id=555)
    LearningProfile.objects.create(user=user, onboarded=True)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    words = [Word.objects.create(unit=unit, en=f"w{i}", uz=f"uz{i}", definition=f"d{i}",
                                 part_of_speech="n.", order=i) for i in range(1, 7)]
    session = DailySession.objects.create(
        user=user, date=timezone.now().date(), status=DailySession.Status.DELIVERED
    )
    for i, w in enumerate(words[:3], start=1):
        SessionWord.objects.create(daily_session=session, word=w, order=i)
    return user, session


@patch("apps.learning.services.exam_deliver.send_quiz_poll")
def test_run_exam_sends_polls_and_records_questions(mock_poll, delivered_session):
    user, session = delivered_session
    mock_poll.side_effect = [f"poll-{i}" for i in range(10)]
    result = exam_deliver.run_exam(user.id)
    assert result is not None
    assert result.status == DailySession.Status.EXAM_SENT
    assert ExamQuestion.objects.filter(daily_session=session).count() == 3
    assert mock_poll.call_count == 3
    result.refresh_from_db()
    assert result.total == 3
    assert result.score == 0


@patch("apps.learning.services.exam_deliver.send_quiz_poll")
def test_run_exam_idempotent_after_exam_sent(mock_poll, delivered_session):
    user, session = delivered_session
    mock_poll.side_effect = [f"poll-{i}" for i in range(10)]
    exam_deliver.run_exam(user.id)
    mock_poll.reset_mock()
    again = exam_deliver.run_exam(user.id)   # session now EXAM_SENT
    assert again is None
    mock_poll.assert_not_called()


@patch("apps.learning.services.exam_deliver.send_quiz_poll")
def test_run_exam_none_when_not_delivered(mock_poll, delivered_session):
    user, session = delivered_session
    session.status = DailySession.Status.PENDING
    session.save()
    assert exam_deliver.run_exam(user.id) is None
    mock_poll.assert_not_called()
