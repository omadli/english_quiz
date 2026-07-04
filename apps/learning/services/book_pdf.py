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
        (i, f"{w.en}  —  {w.uz}   {w.part_of_speech}".strip()) for i, w in enumerate(words, start=1)
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
