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


def get_shared_quiz(token: str) -> SharedQuiz | None:
    """Load a shared quiz from a deep-link payload (`quiz_<pk>` → token is `<pk>`)."""
    return SharedQuiz.objects.filter(pk=int(token)).first() if token.isdigit() else None


def recent_shared_quizzes(telegram_id: int, limit: int = 10) -> list[dict]:
    """Compact cards for the inline-share picker — the user's own recent tests."""
    quizzes = (
        SharedQuiz.objects.filter(created_by_telegram_id=telegram_id)
        .select_related("book")[:limit]
    )
    cards = []
    for q in quizzes:
        book = q.book.title if q.book_id else "—"
        cards.append({
            "id": q.id,
            "title": f"🧠 {book} — {q.question_count} savol",
            "desc": f"{len(q.unit_ids)} bo'lim · {q.interval_seconds}s",
        })
    return cards
