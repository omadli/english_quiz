import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalog.models import Book
from apps.learning.services.book_pdf import active_books, get_sendable_book, save_file_id

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    # FileField writes hit the real filesystem and aren't rolled back by the
    # test-DB transaction; isolate each run under a throwaway MEDIA_ROOT.
    settings.MEDIA_ROOT = tmp_path


def _book(number=1, **kw):
    return Book.objects.create(number=number, title=f"Book {number}", slug=f"book-{number}", **kw)


def test_get_sendable_book_returns_bytes_when_uncached():
    book = _book(pdf=SimpleUploadedFile("b.pdf", b"%PDF-x"))
    name, payload = get_sendable_book(book.id)
    assert name == "Book 1.pdf"
    assert payload == b"%PDF-x"


def test_get_sendable_book_returns_cached_file_id():
    book = _book(pdf=SimpleUploadedFile("b.pdf", b"%PDF-x"), telegram_file_id="ABC123")
    name, payload = get_sendable_book(book.id)
    assert payload == "ABC123"  # no re-upload


def test_get_sendable_book_none_when_no_pdf():
    assert get_sendable_book(_book().id) is None


def test_get_sendable_book_missing_returns_none():
    assert get_sendable_book(999999) is None


def test_save_file_id_persists():
    book = _book(pdf=SimpleUploadedFile("b.pdf", b"%PDF-x"))
    save_file_id(book.id, "XYZ")
    book.refresh_from_db()
    assert book.telegram_file_id == "XYZ"


def test_active_books_ordered():
    _book(2)
    _book(1)
    _book(3, is_active=False)
    assert [b.number for b in active_books()] == [1, 2]
