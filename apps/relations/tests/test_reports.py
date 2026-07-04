import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.learning.models import DailySession
from apps.relations.models import Guardianship
from apps.relations.services.reports import build_learner_report, compute_streak, guardian_wards

pytestmark = pytest.mark.django_db


def test_guardian_wards_lists_active_learners():
    g = User.objects.create(first_name="G")
    l1 = User.objects.create(first_name="L1")
    l2 = User.objects.create(first_name="L2")
    Guardianship.objects.create(guardian=g, learner=l1, role="parent")
    Guardianship.objects.create(
        guardian=g, learner=l2, role="parent", status=Guardianship.Status.REVOKED
    )
    wards = guardian_wards(g)
    assert l1 in wards
    assert l2 not in wards


def test_compute_streak_counts_consecutive_completed_days():
    u = User.objects.create(first_name="U")
    today = timezone.localdate()
    for delta in (0, 1, 2):  # today, yesterday, 2 days ago
        DailySession.objects.create(
            user=u,
            date=today - datetime.timedelta(days=delta),
            status=DailySession.Status.COMPLETED,
        )
    # a gap at day 4 (day 3 missing) shouldn't extend
    DailySession.objects.create(
        user=u, date=today - datetime.timedelta(days=4), status=DailySession.Status.COMPLETED
    )
    assert compute_streak(u) == 3


def test_build_report_with_and_without_data():
    u = User.objects.create(first_name="Ali")
    today = timezone.localdate()
    # no session today
    text = build_learner_report(u, today)
    assert "Ali" in text
    # with a completed session
    DailySession.objects.create(
        user=u, date=today, status=DailySession.Status.COMPLETED, score=8, total=10
    )
    text2 = build_learner_report(u, today)
    assert "8/10" in text2
