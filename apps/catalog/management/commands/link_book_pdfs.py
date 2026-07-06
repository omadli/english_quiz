from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import Book

# Match the volume digit after "Words", e.g. "... Words  4 193p.pdf" -> 4
_VOL_RE = re.compile(r"Words\s+(\d)")


class Command(BaseCommand):
    help = "Point each Book.pdf at the ready PDF in media/books/ (matched by volume number)."

    def handle(self, *args, **opts) -> None:
        books_dir = Path(settings.MEDIA_ROOT) / "books"
        by_number: dict[int, Path] = {}
        for path in sorted(books_dir.glob("*.pdf")):
            match = _VOL_RE.search(path.name)
            if match:
                by_number.setdefault(int(match.group(1)), path)
        if not by_number:
            self.stderr.write(self.style.WARNING(f"No book PDFs found in {books_dir}"))
            return
        for book in Book.objects.order_by("number"):
            path = by_number.get(book.number)
            if path is None:
                self.stderr.write(self.style.WARNING(f"book {book.number}: no PDF file found"))
                continue
            rel = f"books/{path.name}"
            if book.pdf.name != rel:
                book.pdf.name = rel
                book.save(update_fields=["pdf", "updated_at"])
            self.stdout.write(self.style.SUCCESS(f"book {book.number} → {rel}"))
