from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from bot import strings


def main_menu_keyboard(webapp_url: str | None = None) -> ReplyKeyboardMarkup:
    """Bottom menu. ``one_time_keyboard`` so it collapses after a tap instead of
    permanently filling the screen (reopen via the keyboard icon). Adds a Mini App
    WebApp button only when a (https) ``webapp_url`` is set — Telegram rejects
    non-https web_app URLs."""
    rows = [
        [KeyboardButton(text=strings.MENU_TODAY), KeyboardButton(text=strings.MENU_EXAM)],
        [KeyboardButton(text=strings.MENU_TEST), KeyboardButton(text=strings.MENU_WORDS)],
        [KeyboardButton(text=strings.MENU_BOOKS), KeyboardButton(text=strings.MENU_SETTINGS)],
    ]
    if webapp_url:
        rows.append(
            [KeyboardButton(text=strings.MENU_WEBAPP, web_app=WebAppInfo(url=webapp_url))]
        )
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)
