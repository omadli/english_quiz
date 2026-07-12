from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from apps.common.tts import EN_VOICES, UZ_VOICES, voice_label
from bot import strings


def settings_keyboard(profile) -> InlineKeyboardMarkup:
    """Inline settings — each button shows its current value for at-a-glance clarity."""
    audio = strings.BTN_AUDIO_ON if profile.audio_enabled else strings.BTN_AUDIO_OFF
    nudges = strings.BTN_NUDGES_ON if profile.nudges_enabled else strings.BTN_NUDGES_OFF
    days = ", ".join(strings.WEEKDAY_SHORT[d] for d in profile.study_weekdays)
    rows = [
        [InlineKeyboardButton(text=f"🔤 {strings.SETTINGS_WORDS}: {profile.words_per_session}",
                              callback_data="set:words")],
        [InlineKeyboardButton(text=f"📅 {strings.SETTINGS_DAYS}: {days}", callback_data="set:days")],
        [InlineKeyboardButton(text=f"🌅 {strings.SETTINGS_MORNING}: {profile.morning_time:%H:%M}",
                              callback_data="set:morning"),
         InlineKeyboardButton(text=f"🎯 {strings.SETTINGS_EXAM}: {profile.exam_time:%H:%M}",
                              callback_data="set:exam")],
        [InlineKeyboardButton(text=f"🔊 {strings.SETTINGS_AUDIO}: {audio}", callback_data="set:audio")],
        [InlineKeyboardButton(text=f"🇬🇧 {strings.SETTINGS_EN_VOICE}: {voice_label(profile.en_voice)}",
                              callback_data="set:envoice")],
        [InlineKeyboardButton(text=f"🇺🇿 {strings.SETTINGS_UZ_VOICE}: {voice_label(profile.uz_voice)}",
                              callback_data="set:uzvoice")],
        [InlineKeyboardButton(text=f"🔁 {strings.SETTINGS_REPEAT}: {profile.audio_repeat}",
                              callback_data="set:repeat")],
        [InlineKeyboardButton(text=f"🔔 {strings.SETTINGS_NUDGES}: {nudges}",
                              callback_data="set:nudges")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _voice_keyboard(voices, prefix: str, current: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=("✅ " if vid == current else "") + label, callback_data=f"{prefix}:{vid}"
    )] for vid, label in voices]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def en_voice_keyboard(current: str = "") -> InlineKeyboardMarkup:
    return _voice_keyboard(EN_VOICES, "envoice", current)


def uz_voice_keyboard(current: str = "") -> InlineKeyboardMarkup:
    return _voice_keyboard(UZ_VOICES, "uzvoice", current)


def repeat_keyboard(current: int = 0) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=("✅ " if n == current else "") + str(n), callback_data=f"repeat:{n}"
    ) for n in (1, 2, 3)]]
    return InlineKeyboardMarkup(inline_keyboard=rows)
