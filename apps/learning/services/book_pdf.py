from apps.catalog.models import Book


def active_books() -> list:
    return list(Book.objects.filter(is_active=True).order_by("number"))


def get_sendable_book(book_id: int) -> tuple[str, bytes | str] | None:
    """Return (filename, payload) for an active book's PDF, or None if there is none.

    payload is the cached Telegram ``file_id`` (str) when available — so we
    send by id instead of re-uploading — otherwise the raw PDF bytes to upload.

    Inactive books are refused here rather than in each caller: the Mini App
    endpoint and the bot callback both take a book id straight from the client.
    """
    book = Book.objects.filter(pk=book_id, is_active=True).first()
    if book is None or not book.pdf:
        return None
    filename = f"{book.title}.pdf"
    if book.telegram_file_id:
        return (filename, book.telegram_file_id)
    with book.pdf.open("rb") as f:
        return (filename, f.read())


def save_file_id(book_id: int, file_id: str) -> None:
    Book.objects.filter(pk=book_id).update(telegram_file_id=file_id)
