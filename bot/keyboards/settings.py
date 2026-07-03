from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import strings


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✏️ {strings.SETTINGS_WORDS}", callback_data="set:words")],
        [InlineKeyboardButton(text=f"✏️ {strings.SETTINGS_DAYS}", callback_data="set:days")],
        [InlineKeyboardButton(text=f"✏️ {strings.SETTINGS_MORNING}", callback_data="set:morning")],
        [InlineKeyboardButton(text=f"✏️ {strings.SETTINGS_EXAM}", callback_data="set:exam")],
        [InlineKeyboardButton(text=f"✏️ {strings.SETTINGS_AUDIO}", callback_data="set:audio")],
    ])
