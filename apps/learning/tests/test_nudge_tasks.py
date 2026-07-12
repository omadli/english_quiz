from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import TelegramAccount, User
from apps.learning.models import DailySession, LearningProfile
from apps.learning.tasks import dispatch_practice_polls, dispatch_study_nudges

pytestmark = pytest.mark.django_db


def _learner(tid, nudges=True):
    u = User.objects.create(first_name="U")
    LearningProfile.objects.create(user=u, onboarded=True, nudges_enabled=nudges)
    TelegramAccount.objects.create(user=u, telegram_id=tid)
    return u


@patch("apps.learning.tasks.send_text")
def test_dispatch_study_nudges_sends_and_marks(mock_send):
    u = _learner(101)
    s = DailySession.objects.create(user=u, date=timezone.localdate(),
                                    status=DailySession.Status.DELIVERED)
    dispatch_study_nudges()
    assert mock_send.call_count == 1
    assert mock_send.call_args.args[0] == 101
    s.refresh_from_db()
    assert s.study_nudged is True


@patch("apps.learning.tasks.send_quiz_poll")
@patch("apps.learning.tasks.build_questions")
@patch("apps.learning.tasks.pick_practice_word")
@patch("apps.learning.tasks.active_practice_learners")
def test_dispatch_practice_polls_sends_anonymous(mock_learners, mock_pick, mock_build, mock_poll):
    u = _learner(202)
    mock_learners.return_value = [u]
    mock_pick.return_value = object()
    mock_build.return_value = [
        {"prompt": "Q", "options": ["a", "b"], "correct_option": 0, "explanation": "x"}
    ]
    dispatch_practice_polls()
    assert mock_poll.call_count == 1
    assert mock_poll.call_args.kwargs.get("is_anonymous") is True
