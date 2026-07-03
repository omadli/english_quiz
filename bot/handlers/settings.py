from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

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
    return "\n".join([
        strings.SETTINGS_TITLE,
        f"• {strings.SETTINGS_WORDS}: <b>{profile.words_per_session}</b>",
        f"• {strings.SETTINGS_DAYS}: <b>{days}</b>",
        f"• {strings.SETTINGS_MORNING}: <b>{profile.morning_time:%H:%M}</b>",
        f"• {strings.SETTINGS_EXAM}: <b>{profile.exam_time:%H:%M}</b>",
        f"• {strings.SETTINGS_AUDIO}: <b>{audio}</b>",
        "",
        strings.SETTINGS_EDIT_HINT,
    ])


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext, profile: LearningProfile) -> None:
    await state.clear()
    await message.answer(format_profile(profile), reply_markup=settings_keyboard())


@router.callback_query(F.data == "set:words")
async def edit_words(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.words)
    await callback.message.edit_text(strings.ASK_WORDS, reply_markup=words_keyboard())


@router.callback_query(F.data == "set:days")
async def edit_days(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.weekdays)
    await state.update_data(study_weekdays=[])
    await callback.message.edit_text(strings.ASK_WEEKDAYS, reply_markup=weekdays_keyboard([]))


@router.callback_query(F.data == "set:morning")
async def edit_morning(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.morning)
    await callback.message.edit_text(strings.ASK_MORNING, reply_markup=morning_keyboard())


@router.callback_query(F.data == "set:exam")
async def edit_exam(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.exam)
    await callback.message.edit_text(strings.ASK_EXAM, reply_markup=exam_keyboard())


@router.callback_query(F.data == "set:audio")
async def edit_audio(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.audio)
    await callback.message.edit_text(strings.ASK_AUDIO, reply_markup=audio_keyboard())
