from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import strings


def quiz_books_keyboard(books: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=b.title, callback_data=f"pq:book:{b.pk}")] for b in books
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quiz_units_keyboard(units: list) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for u in units:
        row.append(InlineKeyboardButton(text=str(u.number), callback_data=f"pq:unit:{u.pk}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=strings.BTN_BACK, callback_data="pq:books")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
