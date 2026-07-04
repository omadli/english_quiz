import pytest

from apps.catalog.models import Book, Unit, Word
from apps.quiz.models import GroupQuizParticipant, GroupQuizQuestion, GroupQuizSession
from apps.quiz.services import run as run_svc

pytestmark = pytest.mark.django_db


def _configured_session():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    for i in range(6):
        Word.objects.create(unit=unit, en=f"w{i}", uz=f"uz{i}", definition=f"d{i}",
                            part_of_speech="n.", order=i)
    return GroupQuizSession.objects.create(
        chat_id=-100, status=GroupQuizSession.Status.CONFIGURING, book=book,
        unit_ids=[unit.id], question_types=["en_uz"], question_count=3, interval_seconds=10,
    )


def test_prepare_questions_creates_rows_and_runs():
    s = _configured_session()
    run_svc.prepare_questions(s.id)
    s.refresh_from_db()
    assert s.status == GroupQuizSession.Status.RUNNING
    assert GroupQuizQuestion.objects.filter(session=s).count() == 3
    pending = run_svc.pending_questions(s.id)
    assert len(pending) == 3
    assert all(set(p) >= {"id", "prompt", "options", "correct_option"} for p in pending)


def test_record_poll_sent_and_is_aborted():
    s = _configured_session()
    run_svc.prepare_questions(s.id)
    q = GroupQuizQuestion.objects.filter(session=s).first()
    run_svc.record_poll_sent(q.id, "poll-xyz")
    q.refresh_from_db()
    assert q.poll_id == "poll-xyz"
    assert q.sent_at is not None
    assert run_svc.is_aborted(s.id) is False
    s.status = GroupQuizSession.Status.ABORTED
    s.save()
    assert run_svc.is_aborted(s.id) is True


def test_finish_and_leaderboard():
    s = _configured_session()
    run_svc.prepare_questions(s.id)
    GroupQuizParticipant.objects.create(
        session=s, telegram_id=1, full_name="A", correct_count=2, total_time=9
    )
    chat_id, text = run_svc.finish_and_leaderboard(s.id)
    s.refresh_from_db()
    assert chat_id == -100
    assert s.status == GroupQuizSession.Status.FINISHED
    assert "A" in text
