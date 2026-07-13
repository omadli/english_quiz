from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from apps.common.tts import EN_VOICES, UZ_VOICES, voice_label
from bot import strings


def _btn(text: str, cb: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb)


def settings_keyboard(profile) -> InlineKeyboardMarkup:
    """Inline settings — each button shows its current value for at-a-glance clarity."""
    s = strings
    audio = s.BTN_AUDIO_ON if profile.audio_enabled else s.BTN_AUDIO_OFF
    nudges = s.BTN_NUDGES_ON if profile.nudges_enabled else s.BTN_NUDGES_OFF
    days = ", ".join(s.WEEKDAY_SHORT[d] for d in profile.study_weekdays)
    rows = [
        [_btn(f"🔤 {s.SETTINGS_WORDS}: {profile.words_per_session}", "set:words")],
        [_btn(f"📅 {s.SETTINGS_DAYS}: {days}", "set:days")],
        [_btn(f"🌅 {s.SETTINGS_MORNING}: {profile.morning_time:%H:%M}", "set:morning"),
         _btn(f"🎯 {s.SETTINGS_EXAM}: {profile.exam_time:%H:%M}", "set:exam")],
        [_btn(f"🔊 {s.SETTINGS_AUDIO}: {audio}", "set:audio")],
        [_btn(f"🇬🇧 {s.SETTINGS_EN_VOICE}: {voice_label(profile.en_voice)}", "set:envoice")],
        [_btn(f"🇺🇿 {s.SETTINGS_UZ_VOICE}: {voice_label(profile.uz_voice)}", "set:uzvoice")],
        [_btn(f"🔁 {s.SETTINGS_REPEAT}: {profile.audio_repeat}", "set:repeat")],
        [_btn(f"🔔 {s.SETTINGS_NUDGES}: {nudges}", "set:nudges")],
        [_btn(f"🗣 {s.SETTINGS_SPEAKING}: "
              f"{s.BTN_AUDIO_ON if profile.speaking_enabled else s.BTN_AUDIO_OFF}",
              "set:speaking")],
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
