from unittest.mock import patch

import pytest

from apps.accounts.models import User
from apps.learning.models import LearningProfile
from apps.learning.tasks import dispatch_evening_exams

pytestmark = pytest.mark.django_db


@patch("apps.learning.tasks.is_due_for_exam")
@patch("apps.learning.tasks.send_exam")
def test_dispatch_evening_exams_enqueues_due(mock_send, mock_due):
    due = User.objects.create(first_name="Due")
    LearningProfile.objects.create(user=due, onboarded=True)
    skip = User.objects.create(first_name="Skip")
    LearningProfile.objects.create(user=skip, onboarded=True)
    mock_due.side_effect = lambda profile, now: profile.user_id == due.id

    dispatch_evening_exams()

    mock_send.delay.assert_called_once_with(due.id)
