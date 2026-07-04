from unittest.mock import patch

import pytest

from apps.accounts.models import User
from apps.learning.models import LearningProfile
from apps.learning.tasks import dispatch_morning_deliveries

pytestmark = pytest.mark.django_db


@patch("apps.learning.tasks.is_due_for_delivery")
@patch("apps.learning.tasks.deliver_daily_words")
def test_dispatch_enqueues_only_due_users(mock_deliver, mock_due):
    due_user = User.objects.create(first_name="Due")
    LearningProfile.objects.create(user=due_user, onboarded=True)
    skip_user = User.objects.create(first_name="Skip")
    LearningProfile.objects.create(user=skip_user, onboarded=True)

    mock_due.side_effect = lambda profile, now: profile.user_id == due_user.id

    dispatch_morning_deliveries()

    mock_deliver.delay.assert_called_once_with(due_user.id)
