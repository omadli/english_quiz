import datetime

from django.utils import timezone

from apps.learning.models import DailySession
from apps.relations.models import Guardianship


def guardian_wards(guardian) -> list:
    links = (
        Guardianship.objects.filter(guardian=guardian, status=Guardianship.Status.ACTIVE)
        .select_related("learner")
        .order_by("id")
    )
    return [link.learner for link in links]


def compute_streak(learner) -> int:
    dates = set(
        DailySession.objects.filter(user=learner, status=DailySession.Status.COMPLETED).values_list(
            "date", flat=True
        )
    )
    streak = 0
    day = timezone.localdate()
    while day in dates:
        streak += 1
        day -= datetime.timedelta(days=1)
    return streak


def build_learner_report(learner, date) -> str:
    name = learner.full_name or str(learner.pk)
    lines = [f"📊 <b>{name}</b> — {date:%d.%m.%Y}"]
    session = DailySession.objects.filter(user=learner, date=date).first()
    if session is None:
        lines.append("Bugun faoliyat yo'q.")
    else:
        lines.append(f"• So'zlar: {session.words.count()}")
        if session.total:
            lines.append(f"• Imtihon: {session.score or 0}/{session.total}")
        lines.append(f"• Holat: {session.get_status_display()}")
    lines.append(f"🔥 Streak: {compute_streak(learner)} kun")
    return "\n".join(lines)
