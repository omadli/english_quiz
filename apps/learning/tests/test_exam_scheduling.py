import datetime
from unittest.mock import MagicMock

from apps.learning.services.scheduling import is_due_for_exam


def _profile(**kw):
    p = MagicMock()
    p.is_active = kw.get("is_active", True)
    p.onboarded = kw.get("onboarded", True)
    p.timezone = kw.get("timezone", "Asia/Tashkent")
    p.study_weekdays = kw.get("study_weekdays", [0, 1, 2, 3, 4, 5, 6])
    p.exam_time = kw.get("exam_time", datetime.time(20, 0))
    return p


def _utc(hh, mm):
    return datetime.datetime(2026, 7, 6, hh, mm, tzinfo=datetime.UTC)


def test_due_for_exam_when_local_matches():
    # 15:00 UTC = 20:00 Asia/Tashkent (UTC+5), 2026-07-06 Monday
    assert is_due_for_exam(_profile(), _utc(15, 0)) is True


def test_not_due_for_exam_off_minute():
    assert is_due_for_exam(_profile(), _utc(15, 1)) is False
