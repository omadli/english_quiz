import asyncio
import datetime

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.accounts.models import User
from apps.learning.models import LearningProfile, default_weekdays
from apps.quiz.services.share import get_shared_quiz
from apps.relations.services.referral import redeem_token
from bot import strings
from bot.handlers.group_quiz import seed_group_quiz_from_shared
from bot.handlers.menu import menu_keyboard, show_menu
from bot.handlers.quiz_practice import start_shared_quiz
from bot.keyboards.onboarding import intro_keyboard, words_keyboard
from bot.services.users import set_starting_position, update_profile
from bot.states.onboarding import OnboardingStates

router = Router()

DEFAULTS = {
    "words_per_session": 10,
    "study_weekdays": default_weekdays(),
    "morning_time": datetime.time(7, 0),
    "exam_time": datetime.time(20, 0),
    "audio_enabled": True,
    "audio_repeat": 2,
}


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    command: CommandObject,
    user: User,
    profile: LearningProfile,
) -> None:
    await state.clear()
    payload = command.args or ""
    if payload.startswith("quiz_"):
        quiz = await sync_to_async(get_shared_quiz)(payload[len("quiz_"):])
        if quiz is not None:
            if message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                # ?startgroup=quiz_<id> → run it as a group quiz with the ready-check
                await seed_group_quiz_from_shared(
                    message.bot, message.chat.id, message.from_user.id, quiz
                )
            else:
                asyncio.create_task(start_shared_quiz(
                    message.bot, message.chat.id,
                    list(quiz.unit_ids), quiz.question_count,
                    quiz.interval_seconds, list(quiz.question_types),
                ))
            return
    if payload.startswith("g"):
        guardianship = await sync_to_async(redeem_token)(payload[1:], user)
        if guardianship is not None:
            await message.answer(strings.LINKED_OK)
    if profile.onboarded:
        await message.answer(strings.WELCOME_BACK, reply_markup=menu_keyboard())
        return
    await message.answer(strings.WELCOME_NEW, reply_markup=intro_keyboard())


@router.callback_query(F.data == "onb:start")
async def begin_wizard(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.words)
    await callback.message.edit_text(strings.ASK_WORDS, reply_markup=words_keyboard())


@router.callback_query(F.data == "onb:defaults")
async def use_defaults(
    callback: CallbackQuery, state: FSMContext, profile: LearningProfile
) -> None:
    await callback.answer()
    await sync_to_async(update_profile)(profile, onboarded=True, **DEFAULTS)
    await sync_to_async(set_starting_position)(profile)
    await state.clear()
    await callback.message.edit_text(strings.ONBOARD_DONE)
    await show_menu(callback.message)
