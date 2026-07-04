from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def wards_keyboard(wards) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=w.full_name or str(w.pk), callback_data=f"rep:{w.pk}")]
        for w in wards
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
