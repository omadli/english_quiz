from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import Book


class Command(BaseCommand):
    help = (
        "Delete the first page (a copyright/credits page) from books' PDFs and re-render "
        "the cover from the NEW first page. Books 2-6 by default; book 1's first page is the "
        "correct cover, so it's skipped. Run with: uv run --with pymupdf. "
        "NOT idempotent — re-running deletes the real cover, so it requires --apply."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--books", default="2,3,4,5,6", help="comma-separated book numbers")
        parser.add_argument("--apply", action="store_true", help="actually modify (else dry-run)")

    def handle(self, *args, **opts) -> None:
        import fitz  # PyMuPDF — provided via `uv run --with pymupdf`

        numbers = [int(n) for n in opts["books"].split(",") if n.strip()]
        covers_dir = Path(settings.MEDIA_ROOT) / "images" / "books" / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)
        apply = opts["apply"]

        for book in Book.objects.filter(number__in=numbers).order_by("number"):
            if not book.pdf:
                self.stderr.write(self.style.WARNING(f"book {book.number}: no pdf, skip"))
                continue
            pdf_path = Path(settings.MEDIA_ROOT) / book.pdf.name
            doc = fitz.open(pdf_path)
            if doc.page_count < 2:
                self.stderr.write(self.style.WARNING(f"book {book.number}: <2 pages, skip"))
                doc.close()
                continue
            before = doc.page_count
            doc.delete_page(0)  # drop the copyright/credits page → page 2 becomes page 1
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))  # cover from the new first page

            if not apply:
                self.stdout.write(
                    f"[dry] book {book.number}: {before} -> {before - 1} pages, "
                    f"cover would come from new p1 ({pix.width}x{pix.height}). Pass --apply."
                )
                doc.close()
                continue

            tmp = pdf_path.with_suffix(".tmp.pdf")
            doc.save(tmp, garbage=4, deflate=True)
            pix.save(covers_dir / f"{book.slug}.jpg")
            doc.close()
            os.replace(tmp, pdf_path)  # atomic overwrite of the original PDF

            book.telegram_file_id = ""  # PDF changed → force the bot to re-upload
            book.cover.name = f"images/books/covers/{book.slug}.jpg"
            book.save(update_fields=["telegram_file_id", "cover", "updated_at"])
            self.stdout.write(self.style.SUCCESS(
                f"book {book.number}: {before}->{before - 1} pages, "
                "cover re-rendered, file_id cleared"
            ))
