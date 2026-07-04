import datetime
from unittest.mock import MagicMock

from apps.learning.services.scheduling import is_due_for_delivery


def _profile(**kw):
    p = MagicMock()
    p.is_active = kw.get("is_active", True)
    p.onboarded = kw.get("onboarded", True)
    p.timezone = kw.get("timezone", "Asia/Tashkent")
    p.study_weekdays = kw.get("study_weekdays", [0, 1, 2, 3, 4, 5, 6])
    p.morning_time = kw.get("morning_time", datetime.time(7, 0))
    return p


def _utc(y, m, d, hh, mm):
    return datetime.datetime(y, m, d, hh, mm, tzinfo=datetime.UTC)


def test_due_when_local_time_matches():
    # Asia/Tashkent = UTC+5; 02:00 UTC = 07:00 local. 2026-07-06 is a Monday (weekday 0).
    assert is_due_for_delivery(_profile(), _utc(2026, 7, 6, 2, 0)) is True


def test_not_due_off_by_a_minute():
    assert is_due_for_delivery(_profile(), _utc(2026, 7, 6, 2, 1)) is False


def test_not_due_on_non_study_weekday():
    # study only on weekday 2 (Wednesday); 2026-07-06 is Monday.
    assert is_due_for_delivery(_profile(study_weekdays=[2]), _utc(2026, 7, 6, 2, 0)) is False


def test_not_due_when_inactive_or_not_onboarded():
    assert is_due_for_delivery(_profile(is_active=False), _utc(2026, 7, 6, 2, 0)) is False
    assert is_due_for_delivery(_profile(onboarded=False), _utc(2026, 7, 6, 2, 0)) is False
