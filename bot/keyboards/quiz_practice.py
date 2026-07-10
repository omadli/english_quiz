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


def quiz_summary_keyboard(code: str, username: str | None) -> InlineKeyboardMarkup:
    """Summary card actions. `code` self-contains the config; it flows into the
    group startgroup deep-link and the inline share (both charset-safe)."""
    rows = [[InlineKeyboardButton(text=strings.BTN_START_HERE, callback_data="pq:start")]]
    if username:  # startgroup deep-link needs the bot username
        rows.append([InlineKeyboardButton(
            text=strings.BTN_START_GROUP, url=f"https://t.me/{username}?startgroup={code}"
        )])
    # switch_inline_query opens a chat picker and pre-fills the shareable code
    rows.append([InlineKeyboardButton(text=strings.BTN_SHARE, switch_inline_query=code)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shared_card_keyboard(code: str, username: str) -> InlineKeyboardMarkup:
    """Buttons on the inline-shared card: start personal / start in group / re-share."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=strings.BTN_START_HERE, url=f"https://t.me/{username}?start={code}")],
        [InlineKeyboardButton(
            text=strings.BTN_START_GROUP, url=f"https://t.me/{username}?startgroup={code}"
        )],
        [InlineKeyboardButton(text=strings.BTN_SHARE, switch_inline_query=code)],
    ])
