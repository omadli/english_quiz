from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from apps.common.tts import EN_VOICES, UZ_VOICES, voice_label
from bot import strings
from bot.keyboards.common import EXAM_PRESETS, MORNING_PRESETS, WORDS_PRESETS


def _b(text: str, cb: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=cb)


def wards_manage_keyboard(wards) -> InlineKeyboardMarkup:
    rows = [[_b(w.full_name or str(w.pk), f"ward:{w.pk}")] for w in wards]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ward_menu_keyboard(lid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b("⚙️ Sozlamalar", f"wset:{lid}")],
        [_b("📊 Hisobot", f"rep:{lid}")],
        [_b("🗑 Ajratish", f"wrevoke:{lid}")],
    ])


def ward_settings_keyboard(p, lid: int) -> InlineKeyboardMarkup:
    s = strings
    days = ", ".join(s.WEEKDAY_SHORT[d] for d in p.study_weekdays)
    audio = s.BTN_AUDIO_ON if p.audio_enabled else s.BTN_AUDIO_OFF
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(f"🔤 {s.SETTINGS_WORDS}: {p.words_per_session}", f"wsedit:{lid}:words")],
        [_b(f"📅 {s.SETTINGS_DAYS}: {days}", f"wsedit:{lid}:days")],
        [_b(f"🌅 {s.SETTINGS_MORNING}: {p.morning_time:%H:%M}", f"wsedit:{lid}:morning"),
         _b(f"🎯 {s.SETTINGS_EXAM}: {p.exam_time:%H:%M}", f"wsedit:{lid}:exam")],
        [_b(f"🔊 {s.SETTINGS_AUDIO}: {audio}", f"wsedit:{lid}:audio")],
        [_b(f"🇬🇧 {s.SETTINGS_EN_VOICE}: {voice_label(p.en_voice)}", f"wsedit:{lid}:envoice")],
        [_b(f"🇺🇿 {s.SETTINGS_UZ_VOICE}: {voice_label(p.uz_voice)}", f"wsedit:{lid}:uzvoice")],
        [_b(f"🔁 {s.SETTINGS_REPEAT}: {p.audio_repeat}", f"wsedit:{lid}:repeat")],
    ])


def ward_picker(lid: int, field: str, p) -> InlineKeyboardMarkup:
    """Direct-save picker for one ward setting. Values carry no ':' (times use the
    preset index, voice ids are colon-free) so `wsv:<lid>:<field>:<value>` parses cleanly."""
    def row(pairs):
        return [_b(t, f"wsv:{lid}:{field}:{v}") for t, v in pairs]

    if field == "words":
        opts = [(str(n), n) for n in WORDS_PRESETS]
        return InlineKeyboardMarkup(
            inline_keyboard=[row(opts[i:i + 3]) for i in range(0, len(opts), 3)]
        )
    if field in ("morning", "exam"):
        presets = MORNING_PRESETS if field == "morning" else EXAM_PRESETS
        return InlineKeyboardMarkup(inline_keyboard=[row([(t, i) for i, t in enumerate(presets)])])
    if field == "audio":
        return InlineKeyboardMarkup(inline_keyboard=[
            row([(strings.BTN_AUDIO_ON, "on"), (strings.BTN_AUDIO_OFF, "off")])
        ])
    if field == "repeat":
        return InlineKeyboardMarkup(inline_keyboard=[row([(str(n), n) for n in (1, 2, 3)])])
    if field in ("envoice", "uzvoice"):
        voices = EN_VOICES if field == "envoice" else UZ_VOICES
        return InlineKeyboardMarkup(
            inline_keyboard=[[_b(label, f"wsv:{lid}:{field}:{vid}")] for vid, label in voices]
        )
    # days — multi-toggle via wsd:<lid>:<i|done>
    day_btns = [
        _b(("✅ " if i in p.study_weekdays else "") + name, f"wsd:{lid}:{i}")
        for i, name in enumerate(strings.WEEKDAY_SHORT)
    ]
    rows = [day_btns[i:i + 4] for i in range(0, len(day_btns), 4)]
    rows.append([_b(strings.BTN_DONE, f"wsd:{lid}:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
