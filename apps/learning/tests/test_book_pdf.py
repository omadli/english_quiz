import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalog.models import Book, Unit, Word
from apps.learning.services.book_pdf import active_books, build_book_vocab_pdf, get_book_document

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    # Django's FileField writes hit the real filesystem and are NOT rolled back
    # by the test-DB transaction; isolate each test run under a throwaway
    # MEDIA_ROOT so uploaded/generated PDFs never land in the real media/ tree.
    settings.MEDIA_ROOT = tmp_path


def _book(number=1, **kw):
    return Book.objects.create(number=number, title=f"Book {number}", slug=f"book-{number}", **kw)


def _words(book, count):
    unit = Unit.objects.create(book=book, number=1, title="U1")
    for i in range(count):
        Word.objects.create(unit=unit, order=i, en=f"word{i}", uz=f"soz{i}", part_of_speech="n.")


def test_build_pdf_returns_pdf_bytes():
    book = _book()
    _words(book, 30)  # spans >1 page at 22/page
    data = build_book_vocab_pdf(book)
    assert isinstance(data, bytes)
    assert data[:4] == b"%PDF"


def test_build_pdf_empty_book_still_valid():
    book = _book()
    data = build_book_vocab_pdf(book)
    assert data[:4] == b"%PDF"


def test_get_book_document_generates_when_no_pdf():
    book = _book()
    _words(book, 3)
    result = get_book_document(book.id)
    assert result is not None
    name, data = result
    assert name == "book-1-lugat.pdf"
    assert data[:4] == b"%PDF"


def test_get_book_document_serves_uploaded_pdf():
    book = _book(pdf=SimpleUploadedFile("b.pdf", b"%PDF-uploaded"))
    result = get_book_document(book.id)
    assert result is not None
    name, data = result
    assert name == "book-1.pdf"
    assert data == b"%PDF-uploaded"


def test_get_book_document_missing_returns_none():
    assert get_book_document(999999) is None


def test_active_books_ordered():
    _book(2)
    _book(1)
    _book(3, is_active=False)
    books = active_books()
    assert [b.number for b in books] == [1, 2]
