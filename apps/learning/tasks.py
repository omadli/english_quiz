import datetime

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.learning.models import DailySession, LearningProfile
from apps.learning.services.deliver import run_delivery
from apps.learning.services.exam import build_questions
from apps.learning.services.exam_deliver import run_exam
from apps.learning.services.nudges import (
    active_practice_learners,
    due_pre_exam_nudges,
    due_study_nudges,
    mark_pre_exam_nudged,
    mark_study_nudged,
    pick_practice_word,
)
from apps.learning.services.report import finalize_exam
from apps.learning.services.scheduling import is_due_for_delivery, is_due_for_exam
from bot import strings
from bot.sender import send_quiz_poll, send_text


@shared_task
def deliver_daily_words(user_id: int) -> None:
    run_delivery(user_id)


@shared_task
def dispatch_morning_deliveries() -> None:
    now = timezone.now()
    profiles = LearningProfile.objects.filter(is_active=True, onboarded=True)
    for profile in profiles.iterator():
        if is_due_for_delivery(profile, now):
            deliver_daily_words.delay(profile.user_id)


@shared_task
def send_exam(user_id: int) -> None:
    run_exam(user_id)


@shared_task
def dispatch_evening_exams() -> None:
    now = timezone.now()
    for profile in LearningProfile.objects.filter(is_active=True, onboarded=True).iterator():
        if is_due_for_exam(profile, now):
            send_exam.delay(profile.user_id)


@shared_task
def finalize_due_exams() -> None:
    window = datetime.timedelta(minutes=settings.EXAM_WINDOW_MINUTES)
    cutoff = timezone.now() - window
    sessions = DailySession.objects.filter(
        status=DailySession.Status.EXAM_SENT, exam_sent_at__lte=cutoff
    ).select_related("user__telegram")
    for session in sessions.iterator():
        finalize_exam(session)


def _send_text(telegram_id: int, text: str) -> None:
    send_text(telegram_id, text)


@shared_task
def dispatch_study_nudges() -> None:
    for session in due_study_nudges(timezone.localdate()):
        account = getattr(session.user, "telegram", None)
        if account is None or account.blocked_bot:
            continue
        try:
            _send_text(account.telegram_id, strings.NUDGE_STUDY)
        except Exception:  # best-effort
            pass
        mark_study_nudged(session)


@shared_task
def dispatch_pre_exam_nudges() -> None:
    for session in due_pre_exam_nudges(timezone.now()):
        account = getattr(session.user, "telegram", None)
        if account is None or account.blocked_bot:
            continue
        try:
            _send_text(account.telegram_id, strings.NUDGE_PRE_EXAM)
        except Exception:  # best-effort
            pass
        mark_pre_exam_nudged(session)


@shared_task
def dispatch_practice_polls() -> None:
    for learner in active_practice_learners():
        account = getattr(learner, "telegram", None)
        if account is None or account.blocked_bot:
            continue
        word = pick_practice_word(learner)
        if word is None:
            continue
        q = build_questions([word])[0]
        try:
            send_quiz_poll(
                account.telegram_id, q["prompt"], q["options"], q["correct_option"],
                q["explanation"], is_anonymous=True,
            )
        except Exception:  # best-effort
            pass
