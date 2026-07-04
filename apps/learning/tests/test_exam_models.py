import pytest
from django.db import IntegrityError

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, ExamQuestion

pytestmark = pytest.mark.django_db


def _session_and_word():
    user = User.objects.create(first_name="T")
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    session = DailySession.objects.create(user=user, date="2026-07-04")
    return session, word


def test_exam_question_defaults_and_poll_id_unique():
    session, word = _session_and_word()
    q = ExamQuestion.objects.create(
        daily_session=session, word=word, question_type=ExamQuestion.QType.EN_UZ,
        poll_id="poll-1", options=["a", "b", "c", "d"], correct_option=0,
    )
    assert q.chosen_option is None
    assert q.is_correct is None
    assert list(session.questions.all()) == [q]
    with pytest.raises(IntegrityError):
        ExamQuestion.objects.create(
            daily_session=session, word=word, question_type=ExamQuestion.QType.UZ_EN,
            poll_id="poll-1", options=["a"], correct_option=0,
        )


def test_exam_settings_present(settings):
    assert isinstance(settings.EXAM_WINDOW_MINUTES, int)
    assert isinstance(settings.EXAM_REVIEW_CAP, int)
