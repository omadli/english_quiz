import datetime
from zoneinfo import ZoneInfo

from django.conf import settings

from apps.learning.models import DailySession, LearningProfile
from bot import strings


def due_study_nudges(today) -> list[DailySession]:
    return list(
        DailySession.objects.filter(
            date=today,
            status=DailySession.Status.DELIVERED,
            study_nudged=False,
            user__learning_profile__nudges_enabled=True,
        ).select_related("user__telegram")
    )


def is_due_for_pre_exam_nudge(profile: LearningProfile, now_utc: datetime.datetime) -> bool:
    if not profile.is_active or not profile.onboarded:
        return False
    local = now_utc.astimezone(ZoneInfo(profile.timezone))
    if local.weekday() not in profile.study_weekdays:
        return False
    exam_dt = local.replace(
        hour=profile.exam_time.hour, minute=profile.exam_time.minute, second=0, microsecond=0
    )
    target = exam_dt - datetime.timedelta(minutes=settings.PRE_EXAM_NUDGE_MINUTES)
    return local.hour == target.hour and local.minute == target.minute


def due_pre_exam_nudges(now_utc: datetime.datetime) -> list[DailySession]:
    today = now_utc.astimezone(ZoneInfo("Asia/Tashkent")).date()
    candidates = DailySession.objects.filter(
        date=today,
        status=DailySession.Status.DELIVERED,
        pre_exam_nudged=False,
        user__learning_profile__nudges_enabled=True,
    ).select_related("user__telegram", "user__learning_profile")
    return [s for s in candidates if is_due_for_pre_exam_nudge(s.user.learning_profile, now_utc)]


def mark_study_nudged(session: DailySession) -> None:
    DailySession.objects.filter(id=session.id).update(study_nudged=True)


def mark_pre_exam_nudged(session: DailySession) -> None:
    DailySession.objects.filter(id=session.id).update(pre_exam_nudged=True)


def streak_milestone_message(streak: int) -> str | None:
    if streak in settings.STREAK_MILESTONES:
        return strings.NUDGE_STREAK.format(streak=streak)
    return None
