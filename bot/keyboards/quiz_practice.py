from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import strings


def quiz_books_keyboard(books: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=b.title, callback_data=f"pq:book:{b.pk}")] for b in books
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quiz_units_keyboard(units: list, selected: set) -> InlineKeyboardMarkup:
    """Multiselect unit grid: tap to toggle (✅), then «Hammasi» / «Boshlash»."""
    rows = []
    row = []
    for u in units:
        mark = "✅ " if u.pk in selected else ""
        row.append(InlineKeyboardButton(text=f"{mark}{u.number}", callback_data=f"pq:u:{u.pk}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text=strings.BTN_ALL_UNITS, callback_data="pq:all"),
        InlineKeyboardButton(text=strings.BTN_START, callback_data="pq:go"),
    ])
    rows.append([InlineKeyboardButton(text=strings.BTN_BACK, callback_data="pq:books")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
