import pytest
from django.core.management import call_command

from apps.catalog.models import Book

pytestmark = pytest.mark.django_db


@pytest.fixture
def books_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    books_dir = tmp_path / "books"
    books_dir.mkdir()
    for name in (
        "4000 Essential English Words  1.pdf",
        "4000 Essential English Words  4 193p.pdf",
    ):
        (books_dir / name).write_bytes(b"%PDF-x")
    return books_dir


def test_links_pdfs_by_volume_number(books_media):
    Book.objects.create(number=1, title="Book 1", slug="book-1")
    Book.objects.create(number=4, title="Book 4", slug="book-4")

    call_command("link_book_pdfs")

    assert Book.objects.get(number=1).pdf.name == "books/4000 Essential English Words  1.pdf"
    assert Book.objects.get(number=4).pdf.name == "books/4000 Essential English Words  4 193p.pdf"


def test_skips_book_without_matching_file(books_media):
    Book.objects.create(number=2, title="Book 2", slug="book-2")  # no file for vol 2
    call_command("link_book_pdfs")
    assert not Book.objects.get(number=2).pdf
