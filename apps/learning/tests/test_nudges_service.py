import datetime
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.learning.models import DailySession, LearningProfile
from apps.learning.services.nudges import (
    due_pre_exam_nudges,
    due_study_nudges,
    is_due_for_pre_exam_nudge,
    mark_pre_exam_nudged,
    mark_study_nudged,
    streak_milestone_message,
)

pytestmark = pytest.mark.django_db


def _learner(**profile_kw):
    u = User.objects.create(first_name="U")
    LearningProfile.objects.create(user=u, onboarded=True, **profile_kw)
    return u


def test_due_study_nudges_selects_delivered_enabled_unnudged():
    today = timezone.localdate()
    u1 = _learner()  # nudges on
    s1 = DailySession.objects.create(user=u1, date=today, status=DailySession.Status.DELIVERED)
    u2 = _learner(nudges_enabled=False)
    DailySession.objects.create(user=u2, date=today, status=DailySession.Status.DELIVERED)
    u3 = _learner()
    DailySession.objects.create(user=u3, date=today, status=DailySession.Status.COMPLETED)
    u4 = _learner()
    DailySession.objects.create(user=u4, date=today, status=DailySession.Status.DELIVERED,
                                study_nudged=True)
    due = due_study_nudges(today)
    ids = {s.id for s in due}
    assert s1.id in ids
    assert len(ids) == 1  # only u1


def test_mark_study_nudged_persists():
    u = _learner()
    s = DailySession.objects.create(user=u, date=timezone.localdate(),
                                    status=DailySession.Status.DELIVERED)
    mark_study_nudged(s)
    s.refresh_from_db()
    assert s.study_nudged is True


def test_is_due_for_pre_exam_nudge_window():
    # exam at 20:00 Tashkent, PRE_EXAM_NUDGE_MINUTES=30 → due at 19:30 local
    u = _learner(exam_time=datetime.time(20, 0), timezone="Asia/Tashkent",
                 study_weekdays=[0, 1, 2, 3, 4, 5, 6])
    profile = u.learning_profile
    tz = ZoneInfo("Asia/Tashkent")
    due_local = datetime.datetime(2026, 7, 6, 19, 30, tzinfo=tz)  # a Monday
    assert is_due_for_pre_exam_nudge(profile, due_local.astimezone(datetime.UTC)) is True
    off_local = datetime.datetime(2026, 7, 6, 18, 0, tzinfo=tz)
    assert is_due_for_pre_exam_nudge(profile, off_local.astimezone(datetime.UTC)) is False


def test_due_pre_exam_nudges_selects_due_delivered_unnudged():
    # exam at 20:00 Tashkent, PRE_EXAM_NUDGE_MINUTES=30 → due at 19:30 local
    tz = ZoneInfo("Asia/Tashkent")
    due_utc = datetime.datetime(2026, 7, 6, 19, 30, tzinfo=tz).astimezone(datetime.UTC)  # Monday
    today = datetime.date(2026, 7, 6)

    u1 = _learner(exam_time=datetime.time(20, 0), timezone="Asia/Tashkent",
                  study_weekdays=[0, 1, 2, 3, 4, 5, 6])
    s1 = DailySession.objects.create(user=u1, date=today, status=DailySession.Status.DELIVERED)

    u2 = _learner(exam_time=datetime.time(20, 0), timezone="Asia/Tashkent",
                  study_weekdays=[0, 1, 2, 3, 4, 5, 6], nudges_enabled=False)
    DailySession.objects.create(user=u2, date=today, status=DailySession.Status.DELIVERED)

    u3 = _learner(exam_time=datetime.time(20, 0), timezone="Asia/Tashkent",
                  study_weekdays=[0, 1, 2, 3, 4, 5, 6])
    DailySession.objects.create(user=u3, date=today, status=DailySession.Status.DELIVERED,
                                pre_exam_nudged=True)

    u4 = _learner(exam_time=datetime.time(20, 0), timezone="Asia/Tashkent",
                  study_weekdays=[0, 1, 2, 3, 4, 5, 6])
    DailySession.objects.create(user=u4, date=today, status=DailySession.Status.COMPLETED)

    u5 = _learner(exam_time=datetime.time(21, 0), timezone="Asia/Tashkent",
                  study_weekdays=[0, 1, 2, 3, 4, 5, 6])
    DailySession.objects.create(user=u5, date=today, status=DailySession.Status.DELIVERED)

    due = due_pre_exam_nudges(due_utc)
    ids = {s.id for s in due}
    assert s1.id in ids
    assert len(ids) == 1  # only u1


def test_mark_pre_exam_nudged_persists():
    u = _learner()
    s = DailySession.objects.create(user=u, date=timezone.localdate(),
                                    status=DailySession.Status.DELIVERED)
    mark_pre_exam_nudged(s)
    s.refresh_from_db()
    assert s.pre_exam_nudged is True


def test_streak_milestone_message():
    assert streak_milestone_message(7) is not None
    assert "7" in streak_milestone_message(7)
    assert streak_milestone_message(8) is None
