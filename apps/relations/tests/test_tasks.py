from unittest.mock import patch

import pytest

from apps.accounts.models import TelegramAccount, User
from apps.relations.models import Guardianship
from apps.relations.tasks import dispatch_guardian_reports

pytestmark = pytest.mark.django_db


@patch("apps.relations.tasks.send_text")
@patch("apps.relations.tasks.build_learner_report", return_value="RPT")
def test_dispatch_sends_one_report_per_active_ward(mock_build, mock_send):
    guardian = User.objects.create(first_name="G")
    TelegramAccount.objects.create(user=guardian, telegram_id=777)
    l1 = User.objects.create(first_name="L1")
    l2 = User.objects.create(first_name="L2")
    Guardianship.objects.create(guardian=guardian, learner=l1, role="parent")
    Guardianship.objects.create(guardian=guardian, learner=l2, role="parent",
                                status=Guardianship.Status.REVOKED)

    dispatch_guardian_reports()

    # one active ward (l1) → one send to the guardian's telegram
    assert mock_send.call_count == 1
    assert mock_send.call_args.args[0] == 777
