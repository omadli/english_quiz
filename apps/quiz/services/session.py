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
        chat_id=chat_id, started_by_id=user_id, status=GroupQuizSession.Status.CONFIGURING
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
