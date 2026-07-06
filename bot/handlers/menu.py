from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
)
from django.conf import settings as dj_settings

from apps.accounts.models import User
from apps.learning.models import LearningProfile
from bot import strings
from bot.handlers.books import cmd_book
from bot.handlers.leaderboard import cmd_top
from bot.handlers.settings import cmd_settings
from bot.keyboards.menu import main_menu_keyboard

router = Router()


def menu_keyboard() -> ReplyKeyboardMarkup:
    return main_menu_keyboard(dj_settings.WEBAPP_URL or None)


async def show_menu(message: Message, text: str = strings.MENU_OPENED) -> None:
    await message.answer(text, reply_markup=menu_keyboard())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show_menu(message)


@router.message(F.text == strings.MENU_BOOKS)
async def menu_books(message: Message) -> None:
    await cmd_book(message)


@router.message(F.text == strings.MENU_TOP)
async def menu_top(message: Message, user: User) -> None:
    await cmd_top(message, user)


@router.message(F.text == strings.MENU_SETTINGS)
async def menu_settings(message: Message, state: FSMContext, profile: LearningProfile) -> None:
    await cmd_settings(message, state, profile)


@router.message(F.text == strings.MENU_GROUP_QUIZ)
async def menu_group_quiz(message: Message) -> None:
    keyboard = None
    if dj_settings.BOT_USERNAME:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text=strings.GROUP_QUIZ_ADD_BTN,
                    url=f"https://t.me/{dj_settings.BOT_USERNAME}?startgroup=quiz",
                )
            ]]
        )
    await message.answer(strings.GROUP_QUIZ_INFO, reply_markup=keyboard)
