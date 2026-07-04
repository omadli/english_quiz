from django.db.models import F
from django.utils import timezone

from apps.learning.models import DailySession, ExamQuestion
from apps.learning.services.srs import grade_answer


def record_answer(poll_id: str, option_ids: list[int]) -> None:
    """Record a poll answer, apply SM-2, and bump the session score if correct."""
    question = (
        ExamQuestion.objects.select_related("daily_session__user", "word")
        .filter(poll_id=poll_id)
        .first()
    )
    if question is None or question.chosen_option is not None:
        return
    if not option_ids:  # retracted vote
        return

    chosen = option_ids[0]
    question.chosen_option = chosen
    question.is_correct = chosen == question.correct_option
    question.answered_at = timezone.now()
    question.save(update_fields=["chosen_option", "is_correct", "answered_at", "updated_at"])

    grade_answer(question.daily_session.user, question.word, question.is_correct)
    if question.is_correct:
        DailySession.objects.filter(pk=question.daily_session_id).update(score=F("score") + 1)
