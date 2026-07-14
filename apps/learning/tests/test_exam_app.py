import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import (
    DailySession,
    ExamQuestion,
    LearningProfile,
    SessionWord,
    WordProgress,
)
from apps.learning.services import exam_app

pytestmark = pytest.mark.django_db


def _setup(speaking=False):
    user = User.objects.create(first_name="Kid")  # no TelegramAccount → finalize skips send
    profile = LearningProfile.objects.create(user=user, speaking_enabled=speaking)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    words = [
        Word.objects.create(unit=unit, en=f"word{i}", uz=f"soz{i}", definition=f"def{i}", order=i)
        for i in range(1, 9)
    ]
    session = DailySession.objects.create(
        user=user, date=timezone.localdate(), status=DailySession.Status.DELIVERED
    )
    for i, w in enumerate(words[:6], 1):
        SessionWord.objects.create(daily_session=session, word=w, order=i)
    return user, profile, session, words


def test_build_exam_sections_and_no_answer_leak():
    _user, profile, session, _words = _setup()
    data = exam_app.build_exam(session, profile)
    kinds = [s["kind"] for s in data["sections"]]
    assert kinds == ["quiz", "writing", "listening"]  # speaking off by default
    q = data["sections"][0]["questions"][0]
    assert "options" in q and "correct" not in q and "correct_option" not in q  # no leak


def test_build_exam_includes_speaking_when_enabled():
    _user, profile, session, _words = _setup(speaking=True)
    kinds = [s["kind"] for s in exam_app.build_exam(session, profile)["sections"]]
    assert "speaking" in kinds


def test_check_normalizes():
    _user, _p, _s, words = _setup()
    w = words[0]  # en="word1", uz="soz1"
    assert exam_app._check(w, "quiz", "soz1") is True
    assert exam_app._check(w, "writing", "  Word1!  ") is True  # case/punct/space-insensitive
    assert exam_app._check(w, "writing", "wrong") is False
    assert exam_app._check(w, "speaking", "the word is word1 okay") is True  # lenient ASR


def test_submit_exam_grades_finalizes_and_srs():
    user, _p, session, words = _setup()
    answers = [
        {"word_id": words[0].id, "kind": "quiz", "answer": words[0].uz},          # correct
        {"word_id": words[1].id, "kind": "writing", "answer": words[1].en},        # correct
        {"word_id": words[2].id, "kind": "listening", "answer": "totally wrong"},  # wrong
    ]
    result = exam_app.submit_exam(session, answers)
    assert result == {"score": 2, "total": 3}
    session.refresh_from_db()
    assert session.status == DailySession.Status.COMPLETED
    assert ExamQuestion.objects.filter(daily_session=session).count() == 3
    # SM-2 applied per word
    assert WordProgress.objects.filter(user=user, word=words[0]).exists()
    assert WordProgress.objects.get(user=user, word=words[2]).wrong_count == 1
    # Completing the exam marks all its words 'learned' (even the wrong one).
    from apps.learning.models import LearnedWord
    assert LearnedWord.objects.filter(user=user).count() == 3


def test_submit_exam_idempotent_when_completed():
    _user, _p, session, words = _setup()
    exam_app.submit_exam(session, [{"word_id": words[0].id, "kind": "quiz", "answer": words[0].uz}])
    again = exam_app.submit_exam(session, [{"word_id": words[0].id, "kind": "quiz", "answer": "x"}])
    assert again.get("already") is True
    assert ExamQuestion.objects.filter(daily_session=session).count() == 1  # not re-created
