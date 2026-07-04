from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def books_keyboard(books) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=b.title, callback_data=f"pdf:book:{b.pk}")] for b in books]
    return InlineKeyboardMarkup(inline_keyboard=rows)
