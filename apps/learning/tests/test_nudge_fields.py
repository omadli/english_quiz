import pytest

from apps.accounts.models import User
from apps.learning.models import DailySession, LearningProfile

pytestmark = pytest.mark.django_db


def test_nudge_defaults():
    u = User.objects.create(first_name="U")
    profile = LearningProfile.objects.create(user=u)
    assert profile.nudges_enabled is True
    session = DailySession.objects.create(user=u, date="2026-07-04")
    assert session.study_nudged is False
    assert session.pre_exam_nudged is False


def test_settings_present(settings):
    assert isinstance(settings.STUDY_NUDGE_HOUR, int)
    assert isinstance(settings.PRACTICE_POLL_HOUR, int)
    assert isinstance(settings.PRE_EXAM_NUDGE_MINUTES, int)
    assert isinstance(settings.STREAK_MILESTONES, list)
