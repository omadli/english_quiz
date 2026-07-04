import datetime

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.learning.models import DailySession, LearningProfile
from apps.learning.services.deliver import run_delivery
from apps.learning.services.exam_deliver import run_exam
from apps.learning.services.report import finalize_exam
from apps.learning.services.scheduling import is_due_for_delivery, is_due_for_exam


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
