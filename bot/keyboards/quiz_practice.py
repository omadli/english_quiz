from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import strings
from bot.keyboards.group_quiz import COUNTS, INTERVALS


def quiz_books_keyboard(books: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=b.title, callback_data=f"pq:book:{b.pk}")] for b in books
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quiz_units_keyboard(units: list, selected: set) -> InlineKeyboardMarkup:
    rows, row = [], []
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
        InlineKeyboardButton(text=strings.BTN_NEXT_STEP, callback_data="pq:next"),
    ])
    rows.append([InlineKeyboardButton(text=strings.BTN_BACK, callback_data="pq:books")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quiz_count_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=str(n), callback_data=f"pq:count:{n}") for n in COUNTS]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def quiz_time_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=f"{n}s", callback_data=f"pq:time:{n}") for n in INTERVALS]
    return InlineKeyboardMarkup(inline_keyboard=[row[:3], row[3:]])


def quiz_types_keyboard(selected: set) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=("✅ " if code in selected else "") + label, callback_data=f"pq:type:{code}"
        )]
        for code, label in strings.QUIZ_TYPE_LABELS.items()
    ]
    rows.append([InlineKeyboardButton(text=strings.BTN_DONE_TYPES, callback_data="pq:types_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quiz_summary_keyboard(has_group: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=strings.BTN_START_HERE, callback_data="pq:start")]]
    if has_group:  # needs BOT_USERNAME to build the startgroup deep link
        rows.append([InlineKeyboardButton(text=strings.BTN_START_GROUP, callback_data="pq:group")])
    rows.append([InlineKeyboardButton(text=strings.BTN_SHARE, callback_data="pq:share")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
