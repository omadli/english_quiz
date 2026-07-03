from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Book, Unit, Word, parse_pronunciation

BOOK_TITLE = "4000 Essential English Words {n}"


class Command(BaseCommand):
    help = "Import words from data/book{n}.json fixtures into Book/Unit/Word."

    def add_arguments(self, parser):
        parser.add_argument("--book", type=int, default=None, help="Import a single book number")
        parser.add_argument("--dry-run", action="store_true", help="Roll back at the end")
        parser.add_argument("--data-dir", type=str, default=str(settings.BASE_DIR / "data"))

    def handle(self, *args, **opts):
        data_dir = Path(opts["data_dir"])
        book_numbers = [opts["book"]] if opts["book"] else range(1, 7)
        for n in book_numbers:
            path = data_dir / f"book{n}.json"
            if not path.exists():
                self.stderr.write(self.style.WARNING(f"skip: {path} not found"))
                continue
            self._import_book(n, path, opts["dry_run"])

    def _import_book(self, n: int, path: Path, dry_run: bool) -> None:
        records = json.loads(path.read_text(encoding="utf-8"))
        with transaction.atomic():
            book, _ = Book.objects.update_or_create(
                number=n,
                defaults={"title": BOOK_TITLE.format(n=n), "slug": f"book-{n}"},
            )
            units: dict[int, Unit] = {}
            orders: dict[int, int] = {}
            for rec in records:
                f = rec["fields"]
                unit_no = f["unit"]
                unit = units.get(unit_no)
                if unit is None:
                    unit, _ = Unit.objects.update_or_create(
                        book=book,
                        number=unit_no,
                        defaults={
                            "title": f"Unit {unit_no}",
                            "slug": slugify(f"book-{n}-unit-{unit_no}"),
                        },
                    )
                    units[unit_no] = unit
                    orders[unit_no] = 0
                orders[unit_no] += 1
                ipa, pos = parse_pronunciation(f.get("pronunciation"))
                word, _ = Word.objects.update_or_create(
                    unit=unit,
                    en=f["en"],
                    defaults={
                        "uz": f.get("uz") or "",
                        "order": orders[unit_no],
                        "pronunciation": ipa[:100],
                        "part_of_speech": pos[:20],
                        "definition": f.get("definition") or "",
                        "example": f.get("example") or "",
                    },
                )
                image_rel = f.get("image")
                if image_rel and (Path(settings.MEDIA_ROOT) / image_rel).exists():
                    if word.image.name != image_rel:
                        word.image.name = image_rel
                        word.save(update_fields=["image"])
            for unit in units.values():
                unit.word_count = unit.words.count()
                unit.save(update_fields=["word_count"])
            book.word_count = Word.objects.filter(unit__book=book).count()
            book.save(update_fields=["word_count"])
            self.stdout.write(self.style.SUCCESS(f"book {n}: {book.word_count} words"))
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING(f"book {n}: dry-run rolled back"))
