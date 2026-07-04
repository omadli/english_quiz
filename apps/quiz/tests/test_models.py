import pytest
from django.db import IntegrityError

from apps.catalog.models import Book, Unit, Word
from apps.quiz.models import GroupQuizParticipant, GroupQuizQuestion, GroupQuizSession

pytestmark = pytest.mark.django_db


def _session():
    return GroupQuizSession.objects.create(chat_id=-100123, question_count=10)


def test_session_defaults():
    s = _session()
    assert s.status == GroupQuizSession.Status.CONFIGURING
    assert s.unit_ids == []
    assert s.question_types == []
    assert s.interval_seconds == 20


def test_question_and_participant_relations():
    s = _session()
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    q = GroupQuizQuestion.objects.create(
        session=s, word=word, order=1, question_type="en_uz", options=["a"], correct_option=0
    )
    p = GroupQuizParticipant.objects.create(session=s, telegram_id=555, full_name="Ali")
    assert list(s.questions.all()) == [q]
    assert list(s.participants.all()) == [p]
    assert p.correct_count == 0
    assert p.total_time == 0


def test_participant_unique_per_session():
    s = _session()
    GroupQuizParticipant.objects.create(session=s, telegram_id=555)
    with pytest.raises(IntegrityError):
        GroupQuizParticipant.objects.create(session=s, telegram_id=555)
