from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.learning.models import LearningProfile
from bot import strings
from bot.keyboards.onboarding import (
    audio_keyboard,
    audio_repeat_keyboard,
    confirm_keyboard,
    exam_keyboard,
    morning_keyboard,
    weekdays_keyboard,
)
from bot.services.users import apply_wizard_data
from bot.states.onboarding import OnboardingStates
from bot.validators import parse_time, toggle_weekday

router = Router()


def _fmt_time(value: object) -> str:
    return f"{value:%H:%M}" if value else "—"


def format_summary(data: dict) -> str:
    days = ", ".join(strings.WEEKDAY_SHORT[d] for d in data.get("study_weekdays", []))
    audio = strings.BTN_AUDIO_ON if data.get("audio_enabled") else strings.BTN_AUDIO_OFF
    lines = [
        strings.SETTINGS_TITLE,
        f"• {strings.SETTINGS_WORDS}: <b>{data.get('words_per_session')}</b>",
        f"• {strings.SETTINGS_DAYS}: <b>{days}</b>",
        f"• {strings.SETTINGS_MORNING}: <b>{_fmt_time(data.get('morning_time'))}</b>",
        f"• {strings.SETTINGS_EXAM}: <b>{_fmt_time(data.get('exam_time'))}</b>",
        f"• {strings.SETTINGS_AUDIO}: <b>{audio}</b>",
    ]
    return "\n".join(lines)


@router.callback_query(OnboardingStates.words, F.data.startswith("onb:words:"))
async def pick_words(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(words_per_session=int(callback.data.split(":")[-1]))
    await state.set_state(OnboardingStates.weekdays)
    data = await state.get_data()
    await callback.message.edit_text(
        strings.ASK_WEEKDAYS, reply_markup=weekdays_keyboard(data.get("study_weekdays", []))
    )


@router.callback_query(OnboardingStates.weekdays, F.data.regexp(r"^onb:wd:[0-6]$"))
async def toggle_weekday_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    day = int(callback.data.split(":")[-1])
    data = await state.get_data()
    days = toggle_weekday(data.get("study_weekdays", []), day)
    await state.update_data(study_weekdays=days)
    await callback.message.edit_reply_markup(reply_markup=weekdays_keyboard(days))


@router.callback_query(OnboardingStates.weekdays, F.data == "onb:wd:all")
async def weekdays_all(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    days = [0, 1, 2, 3, 4, 5, 6]
    await state.update_data(study_weekdays=days)
    await callback.message.edit_reply_markup(reply_markup=weekdays_keyboard(days))


@router.callback_query(OnboardingStates.weekdays, F.data == "onb:wd:done")
async def weekdays_done(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    if not data.get("study_weekdays"):
        await state.update_data(study_weekdays=[0, 1, 2, 3, 4, 5, 6])
    await state.set_state(OnboardingStates.morning)
    await callback.message.edit_text(strings.ASK_MORNING, reply_markup=morning_keyboard())


@router.callback_query(OnboardingStates.morning, F.data.startswith("onb:mt:"))
async def pick_morning(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    value = callback.data.split("onb:mt:")[-1]
    if value == "other":
        await callback.message.edit_text(strings.ASK_MORNING)
        return
    await state.update_data(morning_time=parse_time(value))
    await state.set_state(OnboardingStates.exam)
    await callback.message.edit_text(strings.ASK_EXAM, reply_markup=exam_keyboard())


@router.message(OnboardingStates.morning)
async def typed_morning(message: Message, state: FSMContext) -> None:
    value = parse_time(message.text or "")
    if value is None:
        await message.answer(strings.INVALID_TIME)
        return
    await state.update_data(morning_time=value)
    await state.set_state(OnboardingStates.exam)
    await message.answer(strings.ASK_EXAM, reply_markup=exam_keyboard())


@router.callback_query(OnboardingStates.exam, F.data.startswith("onb:et:"))
async def pick_exam(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    value = callback.data.split("onb:et:")[-1]
    if value == "other":
        await callback.message.edit_text(strings.ASK_EXAM)
        return
    await state.update_data(exam_time=parse_time(value))
    await state.set_state(OnboardingStates.audio)
    await callback.message.edit_text(strings.ASK_AUDIO, reply_markup=audio_keyboard())


@router.message(OnboardingStates.exam)
async def typed_exam(message: Message, state: FSMContext) -> None:
    value = parse_time(message.text or "")
    if value is None:
        await message.answer(strings.INVALID_TIME)
        return
    await state.update_data(exam_time=value)
    await state.set_state(OnboardingStates.audio)
    await message.answer(strings.ASK_AUDIO, reply_markup=audio_keyboard())


@router.callback_query(OnboardingStates.audio, F.data.in_({"onb:audio:on", "onb:audio:off"}))
async def pick_audio(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    enabled = callback.data.endswith(":on")
    await state.update_data(audio_enabled=enabled)
    if enabled:
        await state.set_state(OnboardingStates.audio_repeat)
        await callback.message.edit_text(
            strings.ASK_AUDIO_REPEAT, reply_markup=audio_repeat_keyboard()
        )
    else:
        await state.update_data(audio_repeat=0)
        await state.set_state(OnboardingStates.confirm)
        data = await state.get_data()
        await callback.message.edit_text(format_summary(data), reply_markup=confirm_keyboard())


@router.callback_query(OnboardingStates.audio_repeat, F.data.startswith("onb:rep:"))
async def pick_audio_repeat(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(audio_repeat=int(callback.data.split(":")[-1]))
    await state.set_state(OnboardingStates.confirm)
    data = await state.get_data()
    await callback.message.edit_text(format_summary(data), reply_markup=confirm_keyboard())


@router.callback_query(OnboardingStates.confirm, F.data == "onb:save")
async def save_wizard(callback: CallbackQuery, state: FSMContext, profile: LearningProfile) -> None:
    await callback.answer()
    data = await state.get_data()
    await sync_to_async(apply_wizard_data)(profile, data)
    await state.clear()
    await callback.message.edit_text(strings.ONBOARD_DONE)
