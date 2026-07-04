from django.utils import timezone

from apps.learning.services.exam import build_questions
from apps.quiz.models import GroupQuizQuestion, GroupQuizSession
from apps.quiz.services.questions import sample_words
from apps.quiz.services.scoring import build_leaderboard

_EXPLANATION = "@essential_words"


def prepare_questions(session_id: int) -> None:
    session = GroupQuizSession.objects.get(id=session_id)
    words = sample_words(session.unit_ids, session.question_count)
    questions = build_questions(words, types=session.question_types or None)
    for order, q in enumerate(questions, start=1):
        GroupQuizQuestion.objects.create(
            session=session, word=q["word"], order=order, question_type=q["question_type"],
            options=q["options"], correct_option=q["correct_option"],
        )
    session.status = GroupQuizSession.Status.RUNNING
    session.started_at = timezone.now()
    session.save(update_fields=["status", "started_at", "updated_at"])


def pending_questions(session_id: int) -> list[dict]:
    items = []
    questions = (
        GroupQuizQuestion.objects.filter(session_id=session_id)
        .select_related("word")
        .order_by("order")
    )
    for q in questions:
        word = q.word
        if q.question_type == "en_uz":
            prompt = f"{word.en} {word.part_of_speech}".strip()
        elif q.question_type == "uz_en":
            prompt = word.uz
        else:
            prompt = word.definition or word.en
        items.append({
            "id": q.id, "prompt": prompt[:300], "options": q.options,
            "correct_option": q.correct_option, "explanation": _EXPLANATION,
        })
    return items


def record_poll_sent(question_id: int, poll_id: str) -> None:
    GroupQuizQuestion.objects.filter(id=question_id).update(poll_id=poll_id, sent_at=timezone.now())


def is_aborted(session_id: int) -> bool:
    return GroupQuizSession.objects.filter(
        id=session_id, status=GroupQuizSession.Status.ABORTED
    ).exists()


def finish_and_leaderboard(session_id: int) -> tuple[int, str]:
    session = GroupQuizSession.objects.get(id=session_id)
    if session.status != GroupQuizSession.Status.ABORTED:
        session.status = GroupQuizSession.Status.FINISHED
        session.finished_at = timezone.now()
        session.save(update_fields=["status", "finished_at", "updated_at"])
    return session.chat_id, build_leaderboard(session)
