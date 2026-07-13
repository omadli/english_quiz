from aiogram.exceptions import TelegramForbiddenError
from django.conf import settings
from django.utils import timezone

from apps.learning.models import DailySession, ExamQuestion
from apps.learning.services.exam import build_questions, select_exam_words
from bot import strings
from bot.sender import send_exam_prompt, send_quiz_poll


def exam_webapp_url() -> str | None:
    base = settings.WEBAPP_URL
    if not base:
        return None
    return f"{base}{'&' if '?' in base else '?'}view=exam"


def prompt_exam(user_id: int) -> DailySession | None:
    """Start-gate: send a '▶️ Boshlash' prompt (opens the sectioned Mini App exam)
    instead of dumping quiz polls. Falls back to the bot-poll exam if no WEBAPP_URL."""
    url = exam_webapp_url()
    if url is None:
        return run_exam(user_id)  # no Mini App configured → the old bot-poll exam
    session = (
        DailySession.objects.select_related("user__telegram")
        .filter(user_id=user_id, status=DailySession.Status.DELIVERED)
        .order_by("-date")
        .first()
    )
    if session is None or session.exam_stage >= 2:
        return None
    account = getattr(session.user, "telegram", None)
    if account is None or account.blocked_bot:
        return None
    try:
        send_exam_prompt(account.telegram_id, strings.EXAM_PROMPT, url)
    except TelegramForbiddenError:
        account.blocked_bot = True
        account.save(update_fields=["blocked_bot", "updated_at"])
        return None
    session.exam_stage = 2
    session.save(update_fields=["exam_stage", "updated_at"])
    return session


def run_exam(user_id: int) -> DailySession | None:
    session = (
        DailySession.objects.select_related("user__telegram")
        .filter(user_id=user_id, status=DailySession.Status.DELIVERED)
        .order_by("-date")
        .first()
    )
    if session is None:
        return None
    account = getattr(session.user, "telegram", None)
    if account is None or account.blocked_bot:
        return None

    words = select_exam_words(session, settings.EXAM_REVIEW_CAP)
    if not words:
        return None

    questions = build_questions(words)
    for q in questions:
        poll_id = send_quiz_poll(
            account.telegram_id, q["prompt"], q["options"], q["correct_option"], q["explanation"]
        )
        ExamQuestion.objects.create(
            daily_session=session,
            word=q["word"],
            question_type=q["question_type"],
            poll_id=poll_id,
            options=q["options"],
            correct_option=q["correct_option"],
        )

    session.status = DailySession.Status.EXAM_SENT
    session.exam_sent_at = timezone.now()
    session.total = len(questions)
    session.score = 0
    session.save(update_fields=["status", "exam_sent_at", "total", "score", "updated_at"])
    return session
