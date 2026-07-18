import logging

from aiogram.exceptions import TelegramForbiddenError
from django.utils import timezone

from apps.learning.models import DailySession, ExamQuestion
from apps.learning.services.nudges import streak_milestone_message
from apps.relations.services.reports import compute_streak
from bot.sender import send_text

logger = logging.getLogger(__name__)


def build_report(session: DailySession) -> str:
    total = session.total or 0
    correct = ExamQuestion.objects.filter(daily_session=session, is_correct=True).count()
    wrong_words = list(
        ExamQuestion.objects.filter(daily_session=session, is_correct=False)
        .select_related("word")
        .values_list("word__en", flat=True)
    )
    unanswered = ExamQuestion.objects.filter(
        daily_session=session, chosen_option__isnull=True
    ).count()

    header = "🏁 <b>Imtihon yakunlandi!</b>"
    if session.completed_late:
        header = "⏳ <b>Kechagi imtihon topshirildi</b> (qarzdorlik yopildi)"
    lines = [header, f"Ball: <b>{correct}/{total}</b>"]
    if wrong_words:
        lines.append("🔁 Takrorlang: " + ", ".join(wrong_words))
    if unanswered:
        lines.append(f"⏭ Javob berilmadi: {unanswered} ta")
    lines.append("Barakalla, shu tarzda davom eting! 💪")
    return "\n".join(lines)


def finalize_exam(session: DailySession) -> None:
    session.score = ExamQuestion.objects.filter(daily_session=session, is_correct=True).count()
    session.status = DailySession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["score", "status", "completed_at", "updated_at"])

    account = getattr(session.user, "telegram", None)
    if account is None or account.blocked_bot:
        return
    try:
        send_text(account.telegram_id, build_report(session))
    except TelegramForbiddenError:
        account.blocked_bot = True
        account.save(update_fields=["blocked_bot", "updated_at"])
    except Exception as exc:
        logger.warning("failed to send exam report for session %s: %s", session.id, exc)

    if not account.blocked_bot and getattr(session.user, "learning_profile", None) \
            and session.user.learning_profile.nudges_enabled:
        message = streak_milestone_message(compute_streak(session.user))
        if message:
            try:
                send_text(account.telegram_id, message)
            except Exception as exc:  # best-effort celebration
                logger.warning("failed to send streak celebration for %s: %s", session.id, exc)
