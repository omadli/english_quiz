import datetime
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.learning.models import DailySession
from apps.learning.tasks import finalize_due_exams

pytestmark = pytest.mark.django_db


@patch("apps.learning.tasks.finalize_exam")
def test_finalize_due_exams_only_past_window(mock_finalize, settings):
    settings.EXAM_WINDOW_MINUTES = 60
    user = User.objects.create(first_name="T")
    old = DailySession.objects.create(
        user=user, date=timezone.now().date(), status=DailySession.Status.EXAM_SENT,
        exam_sent_at=timezone.now() - datetime.timedelta(minutes=90),
    )
    user2 = User.objects.create(first_name="T2")
    recent = DailySession.objects.create(
        user=user2, date=timezone.now().date(), status=DailySession.Status.EXAM_SENT,
        exam_sent_at=timezone.now() - datetime.timedelta(minutes=10),
    )
    finalize_due_exams()
    finalized_ids = [c.args[0].id for c in mock_finalize.call_args_list]
    assert old.id in finalized_ids
    assert recent.id not in finalized_ids
