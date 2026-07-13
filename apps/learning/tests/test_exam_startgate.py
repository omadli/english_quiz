import datetime
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import TelegramAccount, User
from apps.learning.models import DailySession, LearningProfile
from apps.learning.services import exam_deliver
from apps.learning.services.nudges import is_due_for_post_exam_reminder

pytestmark = pytest.mark.django_db


def _user_session():
    user = User.objects.create(first_name="Kid")
    TelegramAccount.objects.create(user=user, telegram_id=77)
    LearningProfile.objects.create(user=user)
    session = DailySession.objects.create(
        user=user, date=timezone.localdate(), status=DailySession.Status.DELIVERED
    )
    return user, session


def test_prompt_exam_sends_button_and_sets_stage(settings):
    settings.WEBAPP_URL = "https://x/webapp/"
    user, session = _user_session()
    with patch.object(exam_deliver, "send_exam_prompt") as send:
        result = exam_deliver.prompt_exam(user.id)
    send.assert_called_once()
    assert "view=exam" in send.call_args.args[2]  # Boshlash opens the Mini App exam
    session.refresh_from_db()
    assert session.exam_stage == 2
    assert session.status == DailySession.Status.DELIVERED  # NOT dumped as polls
    assert result is not None


def test_prompt_exam_skips_when_already_prompted(settings):
    settings.WEBAPP_URL = "https://x/webapp/"
    user, session = _user_session()
    session.exam_stage = 2
    session.save()
    with patch.object(exam_deliver, "send_exam_prompt") as send:
        assert exam_deliver.prompt_exam(user.id) is None
    send.assert_not_called()


def test_prompt_exam_falls_back_to_bot_poll_without_webapp(settings):
    settings.WEBAPP_URL = ""
    user, _session = _user_session()
    with patch.object(exam_deliver, "run_exam", return_value="FALLBACK") as run:
        assert exam_deliver.prompt_exam(user.id) == "FALLBACK"
    run.assert_called_once_with(user.id)


def test_post_exam_reminder_timing():
    user = User.objects.create(first_name="Kid")
    profile = LearningProfile.objects.create(
        user=user, onboarded=True, exam_time=datetime.time(20, 0),
        study_weekdays=[0, 1, 2, 3, 4, 5, 6],
    )
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(profile.timezone)
    at_plus_30 = datetime.datetime(2026, 7, 13, 20, 30, tzinfo=tz).astimezone(datetime.UTC)
    at_exam = datetime.datetime(2026, 7, 13, 20, 0, tzinfo=tz).astimezone(datetime.UTC)
    assert is_due_for_post_exam_reminder(profile, at_plus_30) is True
    assert is_due_for_post_exam_reminder(profile, at_exam) is False
