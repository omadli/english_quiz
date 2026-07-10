from django.utils import timezone

from apps.catalog.models import Book, Unit
from apps.quiz.models import GroupQuizSession

_ACTIVE = (GroupQuizSession.Status.CONFIGURING, GroupQuizSession.Status.RUNNING)


def get_active_session(chat_id: int) -> GroupQuizSession | None:
    return (
        GroupQuizSession.objects.filter(chat_id=chat_id, status__in=_ACTIVE)
        .order_by("-created_at")
        .first()
    )


def start_configuring(chat_id: int, user_id: int) -> GroupQuizSession | None:
    if get_active_session(chat_id) is not None:
        return None
    return GroupQuizSession.objects.create(
        chat_id=chat_id,
        started_by_telegram_id=user_id,
        status=GroupQuizSession.Status.CONFIGURING,
    )


def create_group_session_from_shared(chat_id: int, user_id: int, shared) -> GroupQuizSession | None:
    """Seed a group session from a SharedQuiz (the `?startgroup=quiz_<id>` flow).

    Returns None if a quiz is already active in this chat, mirroring
    ``start_configuring``.
    """
    if get_active_session(chat_id) is not None:
        return None
    return GroupQuizSession.objects.create(
        chat_id=chat_id,
        started_by_telegram_id=user_id,
        status=GroupQuizSession.Status.CONFIGURING,
        book_id=shared.book_id,
        unit_ids=list(shared.unit_ids),
        question_types=list(shared.question_types),
        question_count=shared.question_count,
        interval_seconds=shared.interval_seconds,
    )


def units_for_book(book_number: int) -> list[Unit]:
    return list(Unit.objects.filter(book__number=book_number).order_by("number"))


def set_book(session: GroupQuizSession, book_number: int) -> None:
    book = Book.objects.filter(number=book_number).first()
    session.book = book
    session.unit_ids = []
    session.save(update_fields=["book", "unit_ids", "updated_at"])


def toggle_unit(session: GroupQuizSession, unit_id: int) -> None:
    ids = list(session.unit_ids)
    if unit_id in ids:
        ids.remove(unit_id)
    else:
        ids.append(unit_id)
    session.unit_ids = sorted(ids)
    session.save(update_fields=["unit_ids", "updated_at"])


def toggle_type(session: GroupQuizSession, qtype: str) -> None:
    types = list(session.question_types)
    if qtype in types:
        types.remove(qtype)
    else:
        types.append(qtype)
    session.question_types = types
    session.save(update_fields=["question_types", "updated_at"])


def set_count(session: GroupQuizSession, count: int) -> None:
    session.question_count = count
    session.save(update_fields=["question_count", "updated_at"])


def set_interval(session: GroupQuizSession, seconds: int) -> None:
    session.interval_seconds = seconds
    session.save(update_fields=["interval_seconds", "updated_at"])


def abort_active(chat_id: int) -> bool:
    session = get_active_session(chat_id)
    if session is None:
        return False
    session.status = GroupQuizSession.Status.ABORTED
    session.finished_at = timezone.now()
    session.save(update_fields=["status", "finished_at", "updated_at"])
    return True
