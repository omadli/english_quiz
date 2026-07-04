from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.learning.models import LearningProfile
from bot import strings
from bot.keyboards.onboarding import (
    audio_keyboard,
    exam_keyboard,
    morning_keyboard,
    weekdays_keyboard,
    words_keyboard,
)
from bot.keyboards.settings import settings_keyboard
from bot.states.onboarding import OnboardingStates

router = Router()


def format_profile(profile: LearningProfile) -> str:
    days = ", ".join(strings.WEEKDAY_SHORT[d] for d in profile.study_weekdays)
    audio = strings.BTN_AUDIO_ON if profile.audio_enabled else strings.BTN_AUDIO_OFF
    nudges = strings.BTN_NUDGES_ON if profile.nudges_enabled else strings.BTN_NUDGES_OFF
    return "\n".join([
        strings.SETTINGS_TITLE,
        f"• {strings.SETTINGS_WORDS}: <b>{profile.words_per_session}</b>",
        f"• {strings.SETTINGS_DAYS}: <b>{days}</b>",
        f"• {strings.SETTINGS_MORNING}: <b>{profile.morning_time:%H:%M}</b>",
        f"• {strings.SETTINGS_EXAM}: <b>{profile.exam_time:%H:%M}</b>",
        f"• {strings.SETTINGS_AUDIO}: <b>{audio}</b>",
        f"• {strings.SETTINGS_NUDGES}: <b>{nudges}</b>",
        "",
        strings.SETTINGS_EDIT_HINT,
    ])


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext, profile: LearningProfile) -> None:
    await state.clear()
    await message.answer(format_profile(profile), reply_markup=settings_keyboard())


async def _seed_profile(state: FSMContext, profile: LearningProfile) -> None:
    """Seed all six current settings into FSM state so an edit's confirm summary is complete."""
    await state.update_data(
        words_per_session=profile.words_per_session,
        study_weekdays=list(profile.study_weekdays),
        morning_time=profile.morning_time,
        exam_time=profile.exam_time,
        audio_enabled=profile.audio_enabled,
        audio_repeat=profile.audio_repeat,
    )


@router.callback_query(F.data == "set:words")
async def edit_words(callback: CallbackQuery, state: FSMContext, profile: LearningProfile) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.words)
    await _seed_profile(state, profile)
    await callback.message.edit_text(strings.ASK_WORDS, reply_markup=words_keyboard())


@router.callback_query(F.data == "set:days")
async def edit_days(callback: CallbackQuery, state: FSMContext, profile: LearningProfile) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.weekdays)
    await _seed_profile(state, profile)
    await callback.message.edit_text(
        strings.ASK_WEEKDAYS, reply_markup=weekdays_keyboard(profile.study_weekdays)
    )


@router.callback_query(F.data == "set:morning")
async def edit_morning(
    callback: CallbackQuery, state: FSMContext, profile: LearningProfile
) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.morning)
    await _seed_profile(state, profile)
    await callback.message.edit_text(strings.ASK_MORNING, reply_markup=morning_keyboard())


@router.callback_query(F.data == "set:exam")
async def edit_exam(callback: CallbackQuery, state: FSMContext, profile: LearningProfile) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.exam)
    await _seed_profile(state, profile)
    await callback.message.edit_text(strings.ASK_EXAM, reply_markup=exam_keyboard())


@router.callback_query(F.data == "set:audio")
async def edit_audio(callback: CallbackQuery, state: FSMContext, profile: LearningProfile) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.audio)
    await _seed_profile(state, profile)
    await callback.message.edit_text(strings.ASK_AUDIO, reply_markup=audio_keyboard())


@router.callback_query(F.data == "set:nudges")
async def toggle_nudges(callback: CallbackQuery, profile: LearningProfile) -> None:
    await callback.answer()
    profile.nudges_enabled = not profile.nudges_enabled
    await sync_to_async(profile.save)(update_fields=["nudges_enabled", "updated_at"])
    await callback.message.edit_text(format_profile(profile), reply_markup=settings_keyboard())
