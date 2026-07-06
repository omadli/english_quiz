from apps.catalog.models import Book


def get_book_document(book_id: int) -> tuple[str, bytes] | None:
    """Return (filename, bytes) of the book's uploaded PDF, or None if it has none.

    We only ever serve the real PDF file uploaded to ``Book.pdf`` — no generated
    vocabulary PDF. Link the ready files with ``manage.py link_book_pdfs``.
    """
    book = Book.objects.filter(pk=book_id).first()
    if book is None or not book.pdf:
        return None
    with book.pdf.open("rb") as f:
        return (f"{book.title}.pdf", f.read())


def active_books() -> list:
    return list(Book.objects.filter(is_active=True).order_by("number"))
