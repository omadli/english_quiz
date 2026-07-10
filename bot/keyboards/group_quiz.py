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


_TYPE_LABELS = {"en_uz": "EN→UZ", "uz_en": "UZ→EN", "def_word": "Ta'rif"}
COUNTS = [5, 10, 15, 20, 30]
INTERVALS = [10, 15, 20, 30, 45, 60]


def types_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(
            text=("✅ " if code in selected else "") + label, callback_data=f"gq:type:{code}"
        )
    ] for code, label in _TYPE_LABELS.items()]
    rows.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="gq:types_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def count_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=str(n), callback_data=f"gq:count:{n}") for n in COUNTS]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def interval_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=f"{n}s", callback_data=f"gq:int:{n}") for n in INTERVALS]
    return InlineKeyboardMarkup(inline_keyboard=[row[:3], row[3:]])


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Boshlash", callback_data="gq:start")
    ]])


def ready_keyboard(count: int) -> InlineKeyboardMarkup:
    ready_label = "✅ Men tayyorman" + (f" ({count})" if count else "")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ready_label, callback_data="gq:ready")],
        [InlineKeyboardButton(text="🚀 Boshlash", callback_data="gq:go")],
    ])
