from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import strings
from bot.keyboards.common import EXAM_PRESETS, MORNING_PRESETS, WORDS_PRESETS


def intro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=strings.ONBOARD_START_BTN, callback_data="onb:start")],
        [InlineKeyboardButton(text=strings.ONBOARD_DEFAULTS_BTN, callback_data="onb:defaults")],
    ])


def words_keyboard() -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=str(n), callback_data=f"onb:words:{n}") for n in WORDS_PRESETS]
    rows = [row[i:i + 3] for i in range(0, len(row), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def weekdays_keyboard(selected: list[int]) -> InlineKeyboardMarkup:
    day_buttons = []
    for i, name in enumerate(strings.WEEKDAY_SHORT):
        label = f"✅ {name}" if i in selected else name
        day_buttons.append(InlineKeyboardButton(text=label, callback_data=f"onb:wd:{i}"))
    rows = [day_buttons[i:i + 4] for i in range(0, len(day_buttons), 4)]
    rows.append([
        InlineKeyboardButton(text=strings.BTN_EVERYDAY, callback_data="onb:wd:all"),
        InlineKeyboardButton(text=strings.BTN_DONE, callback_data="onb:wd:done"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def time_keyboard(prefix: str, presets: list[str]) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=t, callback_data=f"{prefix}:{t}") for t in presets]
    return InlineKeyboardMarkup(inline_keyboard=[
        row,
        [InlineKeyboardButton(text=strings.BTN_OTHER, callback_data=f"{prefix}:other")],
    ])


def morning_keyboard() -> InlineKeyboardMarkup:
    return time_keyboard("onb:mt", MORNING_PRESETS)


def exam_keyboard() -> InlineKeyboardMarkup:
    return time_keyboard("onb:et", EXAM_PRESETS)


def audio_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=strings.BTN_AUDIO_ON, callback_data="onb:audio:on"),
        InlineKeyboardButton(text=strings.BTN_AUDIO_OFF, callback_data="onb:audio:off"),
    ]])


def audio_repeat_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=str(n), callback_data=f"onb:rep:{n}") for n in (1, 2, 3)
    ]])


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=strings.BTN_SAVE, callback_data="onb:save")
    ]])
