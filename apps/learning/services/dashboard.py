import datetime

from django.db.models import Count, Q
from django.utils import timezone

from apps.catalog.models import Word
from apps.learning.models import DailySession, ExamQuestion, LearnedWord
from apps.relations.services.reports import compute_streak


def build_dashboard(user, days: int = 30) -> dict:
    """All the learner's stats for the dashboard — learned words, streak, exam
    accuracy (+ trend), most-errored words, missed study days, daily activity."""
    today = timezone.localdate()
    start = today - datetime.timedelta(days=days - 1)

    answered = ExamQuestion.objects.filter(daily_session__user=user, is_correct__isnull=False)
    correct = answered.filter(is_correct=True).count()
    answered_n = answered.count()
    pct = round(correct / answered_n * 100) if answered_n else 0

    trend = [
        {
            "date": r["daily_session__date"].isoformat(),
            "correct": r["correct"],
            "total": r["n"],
            "pct": round(r["correct"] / r["n"] * 100) if r["n"] else 0,
        }
        for r in answered.filter(daily_session__date__gte=start)
        .values("daily_session__date")
        .annotate(n=Count("id"), correct=Count("id", filter=Q(is_correct=True)))
        .order_by("daily_session__date")
    ]

    error_words = [
        {"en": r["word__en"], "uz": r["word__uz"], "wrong": r["wrong"]}
        for r in ExamQuestion.objects.filter(daily_session__user=user, is_correct=False)
        .values("word__en", "word__uz")
        .annotate(wrong=Count("id"))
        .order_by("-wrong")[:10]
    ]

    sessions = {
        s.date: s
        for s in DailySession.objects.filter(user=user, date__gte=start, date__lte=today)
    }
    first_activity = (
        DailySession.objects.filter(user=user)
        .order_by("date")
        .values_list("date", flat=True)
        .first()
    )
    # Reverse O2O DoesNotExist inherits AttributeError, so getattr(..., None) is safe.
    profile = getattr(user, "learning_profile", None)
    study_weekdays = set(profile.study_weekdays) if profile else set()

    activity, missed = [], []
    d = start
    while d <= today:
        s = sessions.get(d)
        activity.append({
            "date": d.isoformat(),
            "status": s.status if s else "none",
            "score": s.score if s else None,
            "total": s.total if s else None,
        })
        completed = s is not None and s.status == DailySession.Status.COMPLETED
        if (
            d < today  # today isn't "missed" yet
            and d.weekday() in study_weekdays
            and first_activity is not None
            and d >= first_activity
            and not completed
        ):
            missed.append(d.isoformat())
        d += datetime.timedelta(days=1)

    return {
        "learned": LearnedWord.objects.filter(user=user).count(),
        "total": Word.objects.count(),
        "streak": compute_streak(user),
        "accuracy": {"correct": correct, "answered": answered_n, "pct": pct},
        "trend": trend,
        "error_words": error_words,
        "missed_days": {"count": len(missed), "dates": missed},
        "activity": activity,
    }
