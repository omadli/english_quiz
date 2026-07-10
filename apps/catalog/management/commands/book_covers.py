from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import Book


class Command(BaseCommand):
    help = "Render each book's PDF first page into Book.cover (run with: uv run --with pymupdf)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--force", action="store_true", help="Re-render even if a cover exists")

    def handle(self, *args, **opts) -> None:
        import fitz  # PyMuPDF — provided via `uv run --with pymupdf`

        covers_dir = Path(settings.MEDIA_ROOT) / "images" / "books" / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)
        for book in Book.objects.order_by("number"):
            if not book.pdf or (book.cover and not opts["force"]):
                continue
            pdf_path = Path(settings.MEDIA_ROOT) / book.pdf.name
            try:
                doc = fitz.open(pdf_path)
                pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom ~ 150dpi
                out = covers_dir / f"{book.slug}.jpg"
                pix.save(out)
                book.cover.name = f"images/books/covers/{book.slug}.jpg"
                book.save(update_fields=["cover", "updated_at"])
                self.stdout.write(
                    self.style.SUCCESS(f"book {book.number}: cover -> {book.cover.name}")
                )
            except Exception as exc:  # noqa: BLE001 - report per-book and continue
                self.stderr.write(self.style.ERROR(f"book {book.number}: {exc}"))
