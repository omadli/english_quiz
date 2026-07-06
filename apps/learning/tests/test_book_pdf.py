import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalog.models import Book
from apps.learning.services.book_pdf import active_books, get_book_document

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    # Django's FileField writes hit the real filesystem and are NOT rolled back
    # by the test-DB transaction; isolate each test run under a throwaway
    # MEDIA_ROOT so uploaded PDFs never land in the real media/ tree.
    settings.MEDIA_ROOT = tmp_path


def _book(number=1, **kw):
    return Book.objects.create(number=number, title=f"Book {number}", slug=f"book-{number}", **kw)


def test_get_book_document_serves_uploaded_pdf():
    book = _book(pdf=SimpleUploadedFile("b.pdf", b"%PDF-uploaded"))
    result = get_book_document(book.id)
    assert result is not None
    name, data = result
    assert name == "Book 1.pdf"
    assert data == b"%PDF-uploaded"


def test_get_book_document_none_when_no_pdf():
    book = _book()  # no PDF attached — we no longer generate one
    assert get_book_document(book.id) is None


def test_get_book_document_missing_returns_none():
    assert get_book_document(999999) is None


def test_active_books_ordered():
    _book(2)
    _book(1)
    _book(3, is_active=False)
    books = active_books()
    assert [b.number for b in books] == [1, 2]
