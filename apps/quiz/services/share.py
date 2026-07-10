from apps.quiz.models import SharedQuiz


def save_shared_quiz(
    telegram_id: int,
    book_id: int | None,
    unit_ids: list[int],
    count: int,
    interval: int,
    types: list[str] | None,
) -> SharedQuiz:
    return SharedQuiz.objects.create(
        created_by_telegram_id=telegram_id,
        book_id=book_id,
        unit_ids=list(unit_ids),
        question_count=count,
        interval_seconds=interval,
        question_types=list(types or []),
    )
    # ponytail: overflow fallback only — a compact share code (quiz_code.py) is the
    # normal path; SharedQuiz rows are created just when a code would exceed 64 chars.
