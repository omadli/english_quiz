import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.accounts.models import User
from apps.relations.services.guardian import active_guardianship, revoke, ward_profile
from apps.relations.services.reports import guardian_wards
from bot import strings
from bot.keyboards.common import EXAM_PRESETS, MORNING_PRESETS
from bot.keyboards.guardian import (
    ward_menu_keyboard,
    ward_picker,
    ward_settings_keyboard,
    wards_manage_keyboard,
)

router = Router()


@router.message(Command("wards"))
async def cmd_wards(message: Message, user: User) -> None:
    wards = await sync_to_async(guardian_wards)(user)
    if not wards:
        await message.answer(strings.NO_WARDS)
        return
    await message.answer(strings.WARDS_PICK, reply_markup=wards_manage_keyboard(wards))


@router.callback_query(F.data.startswith("ward:"))
async def open_ward(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    lid = int(callback.data.split(":")[1])
    link = await sync_to_async(active_guardianship)(user, lid)
    if link is None:
        return
    name = await sync_to_async(lambda: link.learner.full_name or link.learner_id)()
    await callback.message.edit_text(
        strings.WARD_MENU.format(name=name), reply_markup=ward_menu_keyboard(lid)
    )


@router.callback_query(F.data.startswith("wrevoke:"))
async def do_revoke(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    lid = int(callback.data.split(":")[1])
    if await sync_to_async(revoke)(user, lid):
        await callback.message.edit_text(strings.WARD_REVOKED)


async def _render_ward_settings(callback: CallbackQuery, user: User, lid: int) -> None:
    profile = await sync_to_async(ward_profile)(user, lid)
    if profile is None:
        return
    await callback.message.edit_text(
        strings.SETTINGS_TITLE, reply_markup=ward_settings_keyboard(profile, lid)
    )


@router.callback_query(F.data.startswith("wset:"))
async def open_ward_settings(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    await _render_ward_settings(callback, user, int(callback.data.split(":")[1]))


@router.callback_query(F.data.startswith("wsedit:"))
async def edit_ward_field(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    _, lid_s, field = callback.data.split(":")
    lid = int(lid_s)
    profile = await sync_to_async(ward_profile)(user, lid)
    if profile is None:
        return
    await callback.message.edit_text(field, reply_markup=ward_picker(lid, field, profile))


def _apply_value(profile, field: str, value: str) -> list[str]:
    if field == "words":
        profile.words_per_session = int(value)
        return ["words_per_session"]
    if field == "repeat":
        profile.audio_repeat = int(value)
        return ["audio_repeat"]
    if field == "audio":
        profile.audio_enabled = value == "on"
        return ["audio_enabled"]
    if field == "envoice":
        profile.en_voice = value
        return ["en_voice"]
    if field == "uzvoice":
        profile.uz_voice = value
        return ["uz_voice"]
    if field in ("morning", "exam"):
        presets = MORNING_PRESETS if field == "morning" else EXAM_PRESETS
        t = datetime.datetime.strptime(presets[int(value)], "%H:%M").time()
        if field == "morning":
            profile.morning_time = t
            return ["morning_time"]
        profile.exam_time = t
        return ["exam_time"]
    return []


@router.callback_query(F.data.startswith("wsv:"))
async def save_ward_value(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    _, lid_s, field, value = callback.data.split(":", 3)
    lid = int(lid_s)
    profile = await sync_to_async(ward_profile)(user, lid)
    if profile is None:
        return
    fields = _apply_value(profile, field, value)
    if fields:
        await sync_to_async(profile.save)(update_fields=[*fields, "updated_at"])
    await _render_ward_settings(callback, user, lid)


@router.callback_query(F.data.startswith("wsd:"))
async def toggle_ward_day(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    _, lid_s, arg = callback.data.split(":")
    lid = int(lid_s)
    profile = await sync_to_async(ward_profile)(user, lid)
    if profile is None:
        return
    if arg == "done":
        await _render_ward_settings(callback, user, lid)
        return
    days = set(profile.study_weekdays)
    days.symmetric_difference_update({int(arg)})
    profile.study_weekdays = sorted(days)
    await sync_to_async(profile.save)(update_fields=["study_weekdays", "updated_at"])
    await callback.message.edit_reply_markup(reply_markup=ward_picker(lid, "days", profile))
