from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import TelegramAccount, User
from apps.learning.models import DailySession, LearningProfile
from apps.learning.services.report import finalize_exam

pytestmark = pytest.mark.django_db


def _learner(nudges=True):
    u = User.objects.create(first_name="U")
    LearningProfile.objects.create(user=u, onboarded=True, nudges_enabled=nudges)
    TelegramAccount.objects.create(user=u, telegram_id=555)
    return u


@patch("apps.learning.services.report.send_daily")
@patch("apps.learning.services.report.compute_streak", return_value=7)
def test_finalize_sends_streak_celebration_on_milestone(mock_streak, mock_send):
    u = _learner()
    s = DailySession.objects.create(user=u, date=timezone.localdate(),
                                    status=DailySession.Status.EXAM_SENT, total=10)
    finalize_exam(s)
    # one send for the report + one for the streak celebration
    assert mock_send.call_count == 2


@patch("apps.learning.services.report.send_daily")
@patch("apps.learning.services.report.compute_streak", return_value=8)
def test_finalize_no_celebration_when_not_milestone(mock_streak, mock_send):
    u = _learner()
    s = DailySession.objects.create(user=u, date=timezone.localdate(),
                                    status=DailySession.Status.EXAM_SENT, total=10)
    finalize_exam(s)
    assert mock_send.call_count == 1  # report only


@patch("apps.learning.services.report.send_daily")
@patch("apps.learning.services.report.compute_streak", return_value=7)
def test_finalize_no_celebration_when_nudges_disabled(mock_streak, mock_send):
    u = _learner(nudges=False)
    s = DailySession.objects.create(user=u, date=timezone.localdate(),
                                    status=DailySession.Status.EXAM_SENT, total=10)
    finalize_exam(s)
    assert mock_send.call_count == 1  # report only, no celebration
