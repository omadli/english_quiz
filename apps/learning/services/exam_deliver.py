from django.conf import settings
from django.utils import timezone

from apps.learning.models import DailySession, ExamQuestion
from apps.learning.services.exam import build_questions, select_exam_words
from bot.sender import send_quiz_poll


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
