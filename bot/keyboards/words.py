from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import strings


def words_books_keyboard(books: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=b.title, callback_data=f"wl:book:{b.pk}")] for b in books
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def words_units_keyboard(units: list) -> InlineKeyboardMarkup:
    """Unit buttons (3 per row) plus a back-to-books row."""
    rows = []
    row = []
    for u in units:
        row.append(InlineKeyboardButton(text=str(u.number), callback_data=f"wl:unit:{u.pk}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=strings.BTN_BACK, callback_data="wl:books")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def words_back_keyboard(book_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=strings.BTN_BACK, callback_data=f"wl:units:{book_id}")
        ]]
    )
