import datetime
import random
from zoneinfo import ZoneInfo

from django.conf import settings

from apps.accounts.models import User
from apps.catalog.models import Word
from apps.learning.models import DailySession, LearningProfile, WordProgress
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


def is_due_for_post_exam_reminder(profile: LearningProfile, now_utc: datetime.datetime) -> bool:
    """~30 min AFTER exam time, if the exam still isn't done (start-gate reminder)."""
    if not profile.is_active or not profile.onboarded:
        return False
    local = now_utc.astimezone(ZoneInfo(profile.timezone))
    if local.weekday() not in profile.study_weekdays:
        return False
    exam_dt = local.replace(
        hour=profile.exam_time.hour, minute=profile.exam_time.minute, second=0, microsecond=0
    )
    target = exam_dt + datetime.timedelta(minutes=settings.PRE_EXAM_NUDGE_MINUTES)
    return local.hour == target.hour and local.minute == target.minute


def due_post_exam_reminders(now_utc: datetime.datetime) -> list[DailySession]:
    today = now_utc.astimezone(ZoneInfo("Asia/Tashkent")).date()
    candidates = DailySession.objects.filter(
        date=today,
        status=DailySession.Status.DELIVERED,
        exam_stage=2,  # prompted but not yet completed
        user__learning_profile__nudges_enabled=True,
    ).select_related("user__telegram", "user__learning_profile")
    return [
        s for s in candidates
        if is_due_for_post_exam_reminder(s.user.learning_profile, now_utc)
    ]


def mark_exam_stage(session: DailySession, stage: int) -> None:
    DailySession.objects.filter(id=session.id).update(exam_stage=stage)


def mark_study_nudged(session: DailySession) -> None:
    DailySession.objects.filter(id=session.id).update(study_nudged=True)


def mark_pre_exam_nudged(session: DailySession) -> None:
    DailySession.objects.filter(id=session.id).update(pre_exam_nudged=True)


def streak_milestone_message(streak: int) -> str | None:
    if streak in settings.STREAK_MILESTONES:
        return strings.NUDGE_STREAK.format(streak=streak)
    return None


def pick_practice_word(learner) -> Word | None:
    word_ids = list(
        WordProgress.objects.filter(user=learner).values_list("word_id", flat=True)
    )
    if not word_ids:
        return None
    return Word.objects.get(pk=random.choice(word_ids))


def active_practice_learners() -> list:
    return list(
        User.objects.filter(
            learning_profile__nudges_enabled=True, word_progress__isnull=False
        ).distinct()
    )
