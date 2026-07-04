from django.db.models import Count, Sum

from apps.learning.models import DailySession


def _monthly_rows(year: int, month: int) -> list[dict]:
    return list(
        DailySession.objects.filter(
            status=DailySession.Status.COMPLETED,
            date__year=year,
            date__month=month,
            score__isnull=False,
        )
        .values("user", "user__first_name")
        .annotate(points=Sum("score"), sessions=Count("id"))
        .order_by("-points", "-sessions", "user")
    )


def build_monthly_leaderboard(year: int, month: int, limit: int = 10) -> list[dict]:
    return [
        {
            "rank": i + 1,
            "user_id": row["user"],
            "name": row["user__first_name"] or "Anonim",
            "points": row["points"] or 0,
            "sessions": row["sessions"],
        }
        for i, row in enumerate(_monthly_rows(year, month)[:limit])
    ]


def user_month_rank(user, year: int, month: int) -> tuple[int, int] | None:
    for i, row in enumerate(_monthly_rows(year, month)):
        if row["user"] == user.id:
            return (i + 1, row["points"] or 0)
    return None
