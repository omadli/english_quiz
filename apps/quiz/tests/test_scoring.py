import datetime

import pytest
from django.utils import timezone

from apps.catalog.models import Book, Unit, Word
from apps.quiz.models import GroupQuizParticipant, GroupQuizQuestion, GroupQuizSession
from apps.quiz.services.scoring import build_leaderboard, record_group_answer

pytestmark = pytest.mark.django_db


def _question(correct_option=1):
    s = GroupQuizSession.objects.create(chat_id=-100, status=GroupQuizSession.Status.RUNNING)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    q = GroupQuizQuestion.objects.create(
        session=s,
        word=word,
        order=1,
        question_type="en_uz",
        poll_id="gp-1",
        options=["a", "b"],
        correct_option=correct_option,
        sent_at=timezone.now() - datetime.timedelta(seconds=5),
    )
    return s, q


def test_record_group_answer_correct_updates_participant():
    s, q = _question(correct_option=1)
    assert record_group_answer("gp-1", [1], 555, "ali", "Ali") is True
    p = GroupQuizParticipant.objects.get(session=s, telegram_id=555)
    assert p.correct_count == 1
    assert p.total_time > 0  # ~5 seconds


def test_record_group_answer_wrong_no_correct_but_time_counts():
    s, q = _question(correct_option=1)
    record_group_answer("gp-1", [0], 555, "ali", "Ali")
    p = GroupQuizParticipant.objects.get(session=s, telegram_id=555)
    assert p.correct_count == 0
    assert p.total_time > 0


def test_record_group_answer_unknown_poll_returns_false():
    assert record_group_answer("not-a-group-poll", [0], 555, "ali", "Ali") is False


def test_build_leaderboard_orders_by_correct_then_time():
    s = GroupQuizSession.objects.create(chat_id=-100, status=GroupQuizSession.Status.FINISHED)
    GroupQuizParticipant.objects.create(
        session=s, telegram_id=1, full_name="Slow5", correct_count=3, total_time=50
    )
    GroupQuizParticipant.objects.create(
        session=s, telegram_id=2, full_name="Fast5", correct_count=3, total_time=20
    )
    GroupQuizParticipant.objects.create(
        session=s, telegram_id=3, full_name="Two", correct_count=2, total_time=5
    )
    text = build_leaderboard(s)
    # Fast5 (3 correct, 20s) ranks above Slow5 (3 correct, 50s), both above Two (2 correct)
    assert text.index("Fast5") < text.index("Slow5") < text.index("Two")
    assert "🥇" in text
