import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, ExamQuestion, LearnedWord, LearningProfile
from apps.learning.services.dashboard import build_dashboard

pytestmark = pytest.mark.django_db


def _words(n):
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    return [Word.objects.create(unit=unit, en=f"w{i}", uz=f"t{i}", order=i) for i in range(1, n + 1)]


def _session(user, date, status, score=None, total=None):
    return DailySession.objects.create(user=user, date=date, status=status, score=score, total=total)


def test_dashboard_learned_streak_accuracy():
    user = User.objects.create(first_name="Kid")
    LearningProfile.objects.create(user=user, study_weekdays=[0, 1, 2, 3, 4, 5, 6])
    words = _words(5)
    LearnedWord.objects.create(user=user, word=words[0])
    LearnedWord.objects.create(user=user, word=words[1])
    today = timezone.localdate()
    s = _session(user, today, DailySession.Status.COMPLETED, score=2, total=3)
    ExamQuestion.objects.create(daily_session=s, word=words[0], question_type="en_uz",
                                poll_id="p1", correct_option=0, is_correct=True)
    ExamQuestion.objects.create(daily_session=s, word=words[1], question_type="en_uz",
                                poll_id="p2", correct_option=0, is_correct=True)
    ExamQuestion.objects.create(daily_session=s, word=words[2], question_type="en_uz",
                                poll_id="p3", correct_option=0, is_correct=False)
    d = build_dashboard(user)
    assert d["learned"] == 2
    assert d["total"] == 5
    assert d["streak"] == 1
    assert d["accuracy"] == {"correct": 2, "answered": 3, "pct": 67}
    assert d["error_words"][0]["en"] == "w3" and d["error_words"][0]["wrong"] == 1


def test_dashboard_missed_days_respects_studydays_and_first_activity():
    user = User.objects.create(first_name="Kid")
    LearningProfile.objects.create(user=user, study_weekdays=[0, 1, 2, 3, 4, 5, 6])  # every day
    today = timezone.localdate()
    _session(user, today - datetime.timedelta(days=3), DailySession.Status.COMPLETED)  # first activity
    _session(user, today - datetime.timedelta(days=1), DailySession.Status.DELIVERED)  # not completed
    d = build_dashboard(user)
    dates = d["missed_days"]["dates"]
    assert (today - datetime.timedelta(days=1)).isoformat() in dates      # study day, not completed
    assert (today - datetime.timedelta(days=2)).isoformat() in dates      # between first activity & now
    assert (today - datetime.timedelta(days=5)).isoformat() not in dates  # before first activity


def test_dashboard_rest_day_not_missed():
    user = User.objects.create(first_name="Kid")
    today = timezone.localdate()
    rest = today.weekday()  # only today's weekday is a study day → other weekdays are rest days
    LearningProfile.objects.create(user=user, study_weekdays=[rest])
    _session(user, today - datetime.timedelta(days=7), DailySession.Status.COMPLETED)  # first activity
    d = build_dashboard(user)
    assert (today - datetime.timedelta(days=3)).isoformat() not in d["missed_days"]["dates"]


def test_dashboard_empty_user():
    user = User.objects.create(first_name="New")
    LearningProfile.objects.create(user=user)
    d = build_dashboard(user)
    assert d["accuracy"] == {"correct": 0, "answered": 0, "pct": 0}
    assert d["error_words"] == []
    assert d["missed_days"]["count"] == 0
    assert len(d["activity"]) == 30
