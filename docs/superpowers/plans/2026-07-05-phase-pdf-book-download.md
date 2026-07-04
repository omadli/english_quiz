# Faza PDF — Kitobni Yuklab Olish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/book` command that lets a user download a book as a PDF — the uploaded `Book.pdf` if present, else a generated vocabulary PDF built from the book's words.

**Architecture:** A `book_pdf.py` service renders the book's words into a multi-page PDF with Pillow (`Image.save(..., "PDF", save_all=True, append_images=...)`, reusing the existing PIL card-renderer approach — no new heavy dependency), or returns the uploaded `Book.pdf` bytes. A new `/book` handler lists books and sends the chosen PDF via a new `send_document` sender wrapper; the router is the 9th (factory + conftest detach list).

**Tech Stack:** Pillow (existing) multi-page PDF · Django FileField read · aiogram 3.x (command + callback + send_document) · sync_to_async · pytest + pytest-django + pytest-asyncio.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-05-phase-pdf-book-download-design.md`. Phases 0-4c complete on `main`.
- Run via uv (not on PATH): `python -m uv run pytest`, `python -m uv run python manage.py ...`. Postgres + Redis via `docker compose up -d db redis`.
- No new models, no new dependency (Pillow already present). Metric-free.
- `Book` has `number`, `title`, `slug`, `pdf` (FileField, blank/null), `is_active`. `Word` has `unit` FK, `en`, `uz`, `part_of_speech`, `order`; `Unit` has `book` FK, `number`. Words for a book: `Word.objects.filter(unit__book=book).select_related("unit").order_by("unit__number", "order")`.
- `build_book_vocab_pdf(book) -> bytes` — Pillow multi-page PDF (~22 rows/page), always ≥1 page (empty book → one empty page), output starts with `%PDF`.
- `get_book_document(book_id) -> tuple[str, bytes] | None` — uploaded `book.pdf` → `(f"{slug}.pdf", bytes)`; else `(f"{slug}-lugat.pdf", build_book_vocab_pdf(book))`; missing book → None.
- `active_books() -> list[Book]` — `is_active=True` ordered by `number`.
- `send_document(chat_id, data, filename)` — sync wrapper over `bot.send_document(chat_id, BufferedInputFile(data, filename))`, matching the existing `send_daily` pattern.
- Async handlers reach the ORM (and the blocking PDF build / send) ONLY via `sync_to_async`.
- The `/book` router is the 9th — add to BOTH `bot/factory.py` (import + `include_router`) AND `bot/tests/conftest.py`'s `_detach_handler_routers` list (aiogram singleton routers; else the 2nd `build_dispatcher()` raises `RuntimeError`).
- Callback-data: `pdf:book:<id>`.
- OUT of scope: online reading (Phase 5), nicer typography/reportlab, PDF caching.
- TDD; pristine output. Commit footer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

### Prerequisite (once, before Task 1)

```bash
git checkout main && git checkout -b phase-pdf-book-download
```

---

### Task 1: Book PDF service

**Files:**
- Create: `apps/learning/services/book_pdf.py`
- Create: `apps/learning/tests/test_book_pdf.py`

**Interfaces:**
- Consumes: `Book`, `Unit`, `Word` (catalog).
- Produces: `build_book_vocab_pdf(book) -> bytes`, `get_book_document(book_id) -> tuple[str, bytes] | None`, `active_books() -> list`.

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_book_pdf.py`:
```python
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalog.models import Book, Unit, Word
from apps.learning.services.book_pdf import active_books, build_book_vocab_pdf, get_book_document

pytestmark = pytest.mark.django_db


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
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_book_pdf.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/learning/services/book_pdf.py`**

```python
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from apps.catalog.models import Book, Word

_WIDTH = 720
_ROW_H = 28
_PAD = 24
_ROWS_PER_PAGE = 22


def _render_page(title: str, rows: list[tuple[int, str]]) -> Image.Image:
    height = _PAD * 2 + _ROW_H * (len(rows) + 2)
    img = Image.new("RGB", (_WIDTH, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    draw.text((_PAD, _PAD), title, fill="black", font=font)
    y = _PAD + _ROW_H * 2
    for index, line in rows:
        draw.text((_PAD, y), f"{index}. {line}", fill="black", font=font)
        y += _ROW_H
    return img


def build_book_vocab_pdf(book: Book) -> bytes:
    words = list(
        Word.objects.filter(unit__book=book)
        .select_related("unit")
        .order_by("unit__number", "order")
    )
    rows = [
        (i, f"{w.en}  —  {w.uz}   {w.part_of_speech}".strip())
        for i, w in enumerate(words, start=1)
    ]
    pages = [
        _render_page(book.title, rows[start : start + _ROWS_PER_PAGE])
        for start in range(0, max(len(rows), 1), _ROWS_PER_PAGE)
    ]
    buf = BytesIO()
    pages[0].save(buf, format="PDF", save_all=True, append_images=pages[1:])
    return buf.getvalue()


def get_book_document(book_id: int) -> tuple[str, bytes] | None:
    book = Book.objects.filter(pk=book_id).first()
    if book is None:
        return None
    if book.pdf:
        with book.pdf.open("rb") as f:
            return (f"{book.slug}.pdf", f.read())
    return (f"{book.slug}-lugat.pdf", build_book_vocab_pdf(book))


def active_books() -> list:
    return list(Book.objects.filter(is_active=True).order_by("number"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_book_pdf.py -v`
Expected: all PASS.

- [ ] **Step 5: Full suite + ruff + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/services/book_pdf.py apps/learning/tests/test_book_pdf.py
git commit -m "feat(learning): book vocabulary PDF generation service"
```
Expected: full suite passes (199 prior + 6 new = 205); ruff clean.

---

### Task 2: `send_document` sender

**Files:**
- Modify: `bot/sender.py`
- Create: `bot/tests/test_sender_document.py`

**Interfaces:**
- Produces: `bot.sender.send_document(chat_id, data: bytes, filename: str) -> None`.

- [ ] **Step 1: Write the failing test**

`bot/tests/test_sender_document.py`:
```python
from unittest.mock import AsyncMock, patch

import pytest

from bot import sender

pytestmark = pytest.mark.asyncio


@patch("bot.sender._make_bot")
async def test_send_document_calls_bot(mock_make_bot):
    bot = AsyncMock()
    mock_make_bot.return_value = bot
    import asyncio

    await asyncio.to_thread(sender.send_document, 42, b"%PDF-x", "book.pdf")
    assert bot.send_document.await_count == 1
    args = bot.send_document.call_args.args
    assert args[0] == 42  # chat_id
    # the document arg is a BufferedInputFile with our filename
    assert args[1].filename == "book.pdf"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_sender_document.py -v`
Expected: FAIL — `send_document` missing.

- [ ] **Step 3: Add `send_document` to `bot/sender.py`**

`BufferedInputFile` is already imported at the top of `bot/sender.py`. Add:
```python
async def _send_document(bot: Bot, chat_id: int, data: bytes, filename: str) -> None:
    await bot.send_document(chat_id, BufferedInputFile(data, filename))


def send_document(chat_id: int, data: bytes, filename: str) -> None:
    async def _run() -> None:
        bot = _make_bot()
        try:
            await _send_document(bot, chat_id, data, filename)
        finally:
            await bot.session.close()

    asyncio.run(_run())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_sender_document.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + ruff + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/sender.py bot/tests/test_sender_document.py
git commit -m "feat(bot): send_document sender wrapper"
```

---

### Task 3: `/book` handler + keyboard

**Files:**
- Create: `bot/handlers/books.py`, `bot/keyboards/books.py`
- Modify: `bot/strings.py`
- Create: `bot/tests/test_handlers_books.py`

**Interfaces:**
- Consumes: `active_books`/`get_book_document` (Task 1), `send_document` (Task 2).
- Produces: `bot.handlers.books.router` with `/book` + `pdf:book:<id>`; `bot.keyboards.books.books_keyboard(books)`.

- [ ] **Step 1: Write the failing tests**

`bot/tests/test_handlers_books.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import books

pytestmark = pytest.mark.asyncio


@patch("bot.handlers.books.active_books")
async def test_cmd_book_lists_books(mock_books):
    b = MagicMock()
    b.pk = 1
    b.title = "Book 1"
    mock_books.return_value = [b]
    message = AsyncMock()
    await books.cmd_book(message)
    message.answer.assert_awaited()


@patch("bot.handlers.books.active_books", return_value=[])
async def test_cmd_book_no_books(mock_books):
    message = AsyncMock()
    await books.cmd_book(message)
    message.answer.assert_awaited()


@patch("bot.handlers.books.send_document")
@patch("bot.handlers.books.get_book_document")
async def test_send_pdf_sends_document(mock_get, mock_send):
    mock_get.return_value = ("book-1-lugat.pdf", b"%PDF-x")
    callback = AsyncMock()
    callback.data = "pdf:book:1"
    callback.message.chat.id = 55
    await books.send_pdf(callback)
    mock_send.assert_called_once()
    assert mock_send.call_args.args[0] == 55
    assert mock_send.call_args.args[2] == "book-1-lugat.pdf"


@patch("bot.handlers.books.send_document")
@patch("bot.handlers.books.get_book_document", return_value=None)
async def test_send_pdf_missing_book(mock_get, mock_send):
    callback = AsyncMock()
    callback.data = "pdf:book:999"
    await books.send_pdf(callback)
    mock_send.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_handlers_books.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Add strings + keyboard**

In `bot/strings.py`, add:
```python
PICK_BOOK_PDF = "📚 Qaysi kitobni PDF sifatida yuklab olasiz?"
NO_BOOKS = "Hozircha kitob mavjud emas."
PDF_SENDING = "⏳ Tayyorlanmoqda..."
PDF_ERROR = "Kechirasiz, PDF yuborishda xatolik yuz berdi."
```

`bot/keyboards/books.py`:
```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def books_keyboard(books) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=b.title, callback_data=f"pdf:book:{b.pk}")]
        for b in books
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
```

- [ ] **Step 4: Implement `bot/handlers/books.py`**

```python
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.learning.services.book_pdf import active_books, get_book_document
from bot import strings
from bot.keyboards.books import books_keyboard
from bot.sender import send_document

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("book"))
async def cmd_book(message: Message) -> None:
    books = await sync_to_async(active_books)()
    if not books:
        await message.answer(strings.NO_BOOKS)
        return
    await message.answer(strings.PICK_BOOK_PDF, reply_markup=books_keyboard(books))


@router.callback_query(F.data.startswith("pdf:book:"))
async def send_pdf(callback: CallbackQuery) -> None:
    await callback.answer(strings.PDF_SENDING)
    book_id = int(callback.data.split(":")[-1])
    doc = await sync_to_async(get_book_document)(book_id)
    if doc is None:
        return
    filename, data = doc
    try:
        await sync_to_async(send_document)(callback.message.chat.id, data, filename)
    except Exception as exc:  # best-effort
        logger.warning("failed to send book pdf %s: %s", book_id, exc)
        await callback.message.answer(strings.PDF_ERROR)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_handlers_books.py -v`
Expected: all PASS.

- [ ] **Step 6: Full suite + ruff + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/handlers/books.py bot/keyboards/books.py bot/strings.py bot/tests/test_handlers_books.py
git commit -m "feat(bot): /book PDF download command"
```

---

### Task 4: Wire router + conftest + docs + gate

**Files:**
- Modify: `bot/factory.py`, `bot/tests/conftest.py`, `Readme.md`
- Create: `bot/tests/test_factory_books.py`

**Interfaces:**
- Produces: `books.router` included in `build_dispatcher` (9th router); documented usage.

- [ ] **Step 1: Write the failing test**

`bot/tests/test_factory_books.py`:
```python
def test_dispatcher_includes_books_router(settings):
    settings.REDIS_URL = "redis://localhost:6379/1"
    from bot.factory import build_dispatcher

    dp = build_dispatcher()
    assert len(dp.sub_routers) >= 9  # + books
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_factory_books.py -v`
Expected: FAIL — only 8 routers wired.

- [ ] **Step 3: Wire the router in `bot/factory.py`**

Add `books` to the handlers import (alphabetical — it sorts first):
```python
from bot.handlers import (
    books,
    common,
    group_quiz,
    leaderboard,
    onboarding,
    quiz,
    relations,
    settings,
    start,
)
```
and, in `build_dispatcher`, after `dp.include_router(leaderboard.router)`:
```python
    dp.include_router(books.router)
```

- [ ] **Step 4: Update `bot/tests/conftest.py`**

In `_detach_handler_routers`, add `books` to BOTH the `from bot.handlers import ...` line AND the module list/tuple the loop iterates (alphabetical — first). Read the file first to match its exact style.

- [ ] **Step 5: Run the factory tests**

Run: `python -m uv run pytest bot/tests/test_factory_books.py bot/tests/test_factory.py bot/tests/test_factory_leaderboard.py -v`
Expected: PASS (≥9, and the existing checks still hold).

- [ ] **Step 6: Update `Readme.md`**

Add a "Book PDF download" subsection under the Bot section:
```markdown
## Book PDF download

Users send `/book` and pick a volume to download it as a PDF — the uploaded
`Book.pdf` if one exists, otherwise a vocabulary PDF generated on the fly from
the book's words.
```

- [ ] **Step 7: Full gate + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/factory.py bot/tests/conftest.py Readme.md bot/tests/test_factory_books.py
git commit -m "feat(bot): wire books router into dispatcher + docs"
```
Expected: full suite passes; ruff clean whole-repo.

---

## Self-Review (completed by plan author)

**Spec coverage** — every spec section maps to a task:
- §4 services (build_book_vocab_pdf, get_book_document, active_books) → Task 1
- §5 sender (send_document) → Task 2
- §5 handler (/book, pdf:book callback, keyboard) → Task 3
- §5 wiring (factory + conftest) → Task 4
- §6 tests → each task ships tests; sender/PDF-send mocked
- §8 DoD → Task 4 gate

**Placeholder scan** — no TBD/TODO. The 9th-router conftest update is explicit in Task 4 Step 4. The blocking PDF build + send are wrapped in `sync_to_async` in the async handler (Task 3).

**Type/name consistency** — `build_book_vocab_pdf`/`get_book_document`/`active_books` (Task 1) consumed with matching names + patch sites (`bot.handlers.books.*`) in Task 3; `send_document` (Task 2) imported by name into the handler (patchable). `get_book_document` returns `(filename, bytes)` consumed as `filename, data = doc`. Callback `pdf:book:<id>` parsed via `split(":")[-1]`. `books_keyboard(books)` uses `b.title`/`b.pk` matching the `Book` fields.

**Ordering note** — `docker compose up -d db redis` for the DB tests (Task 1) and the factory test (Task 4, needs Redis). Task 4 adds the 9th router; the conftest detach-list update is REQUIRED or the full suite's second `build_dispatcher()` raises `RuntimeError`. `book.pdf.open("rb")` in `get_book_document` reads the FileField via default storage (works in tests with `SimpleUploadedFile`).
