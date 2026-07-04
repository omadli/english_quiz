import datetime

import pytest

from apps.accounts.models import User
from apps.learning.models import DailySession
from apps.learning.services.ranking import build_monthly_leaderboard, user_month_rank

pytestmark = pytest.mark.django_db


def _completed(user, day, score):
    DailySession.objects.create(
        user=user, date=day, status=DailySession.Status.COMPLETED, score=score, total=10
    )


def test_leaderboard_orders_by_points_then_sessions():
    alice = User.objects.create(first_name="Alice")
    bob = User.objects.create(first_name="Bob")
    carol = User.objects.create(first_name="Carol")
    # Alice: 8 (one session). Bob: 8 across two sessions -> ties points, more sessions => ahead.
    _completed(alice, datetime.date(2026, 7, 2), 8)
    _completed(bob, datetime.date(2026, 7, 2), 5)
    _completed(bob, datetime.date(2026, 7, 3), 3)
    _completed(carol, datetime.date(2026, 7, 2), 10)
    board = build_monthly_leaderboard(2026, 7, limit=10)
    names = [e["name"] for e in board]
    assert names == ["Carol", "Bob", "Alice"]  # 10 ; 8/2sess ; 8/1sess
    assert board[0]["rank"] == 1
    assert board[1]["points"] == 8
    assert board[1]["sessions"] == 2


def test_leaderboard_excludes_other_months_and_incomplete():
    alice = User.objects.create(first_name="Alice")
    _completed(alice, datetime.date(2026, 7, 5), 7)
    _completed(alice, datetime.date(2026, 6, 5), 9)  # other month
    DailySession.objects.create(  # incomplete this month
        user=alice, date=datetime.date(2026, 7, 6), status=DailySession.Status.DELIVERED
    )
    board = build_monthly_leaderboard(2026, 7)
    assert len(board) == 1
    assert board[0]["points"] == 7  # only the July completed one


def test_leaderboard_limit():
    for i in range(5):
        u = User.objects.create(first_name=f"U{i}")
        _completed(u, datetime.date(2026, 7, 2), i + 1)
    assert len(build_monthly_leaderboard(2026, 7, limit=3)) == 3


def test_user_month_rank():
    users = []
    for i in range(12):
        u = User.objects.create(first_name=f"U{i}")
        _completed(u, datetime.date(2026, 7, 2), 100 - i)  # U0 highest ... U11 lowest
        users.append(u)
    # U0 rank 1, U11 rank 12 (beyond a top-10 view)
    assert user_month_rank(users[0], 2026, 7) == (1, 100)
    assert user_month_rank(users[11], 2026, 7)[0] == 12
    # a non-participant
    outsider = User.objects.create(first_name="Out")
    assert user_month_rank(outsider, 2026, 7) is None
