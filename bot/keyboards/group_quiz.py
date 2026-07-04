from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from apps.quiz.services.session import units_for_book

BOOK_NUMBERS = [1, 2, 3, 4, 5, 6]


def books_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=str(n), callback_data=f"gq:book:{n}") for n in BOOK_NUMBERS]
    return InlineKeyboardMarkup(inline_keyboard=[row[:3], row[3:]])


def units_keyboard(book_number: int, selected: list[int]) -> InlineKeyboardMarkup:
    buttons = []
    for unit in units_for_book(book_number):
        mark = "✅ " if unit.id in selected else ""
        buttons.append(
            InlineKeyboardButton(
                text=f"{mark}Unit {unit.number}", callback_data=f"gq:unit:{unit.id}"
            )
        )
    rows = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
    rows.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="gq:units_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
