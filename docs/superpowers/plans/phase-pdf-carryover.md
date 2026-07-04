# PDF Book-Download → Later — Carryover Notes

Deferred items from the PDF book-download phase review. None are defects; the final whole-branch review confirmed the flow is consistent end-to-end, blocking work (PDF build + send) is offloaded via `sync_to_async`, the empty-book edge is handled, and the 9th router is wired with no collision — merge-ready. The one Important (a test writing to the real `media/` dir) was FIXED before merge (a `tmp_path` MEDIA_ROOT autouse fixture). The rest below are genuine defers.

## Performance / caching (before scale)
- **Whole-book vocab PDF is rendered synchronously per `/book` tap** (~27 Pillow pages for ~600 words), with NO caching. Because `sync_to_async` is `thread_sensitive=True` by default, a heavy render occupies the shared sync worker thread and briefly serializes other `sync_to_async` ORM calls bot-wide (the event loop stays free). For scale: cache the generated PDF (store into `Book.pdf` on first generation, or a Redis/file cache keyed by book + word-set hash), and/or offload to a Celery task that sends the document when ready.

## Quality / typography
- **`load_default()` bitmap font** (consistent with the daily card renderer) produces a functional but plain PDF; Uzbek `o'`/`g'` share the card-renderer's rendering limitation. A nicer PDF (reportlab or a bundled TTF via fpdf2, proper columns/headers per unit) is a future polish.
- **No per-unit grouping** in the generated PDF — words are a flat numbered list ordered by `unit__number, order`. Unit-header rows would improve readability.

## Test-coverage gaps (add on next touch)
- `test_build_pdf_returns_pdf_bytes` asserts only the `%PDF` magic, not the actual page count (a regression collapsing `append_images` to one page wouldn't be caught).
- `cmd_book` list/no-books tests assert only that `answer` was awaited, not WHICH string or that `books_keyboard` was attached.
- `send_pdf`'s `callback.answer` + `int(callback.data.split(":")[-1])` parse sit outside the try/except — unreachable via normal buttons (the `startswith` filter + bot-generated `pdf:book:<pk>` payload), and aiogram's dispatcher catches any hand-crafted `ValueError`, so not a crash risk; wrap defensively if desired.

## Feature scope
- **Per-unit / per-range download** — currently only whole-book. A unit picker (book → unit → PDF) would give lighter, faster downloads.
- **`Book.pdf` population** — the uploaded-PDF branch only fires once volume PDFs are actually uploaded to `Book.pdf`; until then every download is generated. An import/admin step to attach the official volume PDFs would make the primary path live.
