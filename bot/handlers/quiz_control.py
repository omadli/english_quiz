"""/pause — pause a live quiz (personal or group) with Resume / Stop buttons.

The pause takes effect at the next question boundary (native quiz polls can't be
paused mid-poll). In groups only admins may control the quiz, like /stop.
"""

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from asgiref.sync import sync_to_async

from apps.quiz.services.session import abort_active
from bot import strings
from bot.quiz_control import get_control

router = Router()


def _pause_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=strings.QUIZ_PAUSE_RESUME_BTN, callback_data="qc:resume"),
        InlineKeyboardButton(text=strings.QUIZ_PAUSE_STOP_BTN, callback_data="qc:stop"),
    ]])


def _is_group(chat_type: str) -> bool:
    return chat_type in (ChatType.GROUP, ChatType.SUPERGROUP)


async def _is_admin(bot, chat_id: int, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")


@router.message(Command("pause"))
async def cmd_pause(message: Message) -> None:
    if _is_group(message.chat.type) and not await _is_admin(
        message.bot, message.chat.id, message.from_user.id
    ):
        await message.answer(strings.QUIZ_PAUSE_ADMIN)
        return
    control = get_control(message.chat.id)
    if control is None or control.stopped:
        await message.answer(strings.QUIZ_PAUSE_NONE)
        return
    control.pause()
    await message.answer(strings.QUIZ_PAUSED_MSG, reply_markup=_pause_keyboard())


@router.callback_query(F.data == "qc:resume")
async def cb_resume(callback: CallbackQuery) -> None:
    if _is_group(callback.message.chat.type) and not await _is_admin(
        callback.bot, callback.message.chat.id, callback.from_user.id
    ):
        await callback.answer(strings.QUIZ_PAUSE_ADMIN, show_alert=True)
        return
    control = get_control(callback.message.chat.id)
    if control is None or control.stopped:
        await callback.answer(strings.QUIZ_PAUSE_NONE, show_alert=True)
        return
    control.resume()
    await callback.answer()
    await callback.message.edit_text(strings.QUIZ_RESUMED_MSG)


@router.callback_query(F.data == "qc:stop")
async def cb_stop(callback: CallbackQuery) -> None:
    if _is_group(callback.message.chat.type) and not await _is_admin(
        callback.bot, callback.message.chat.id, callback.from_user.id
    ):
        await callback.answer(strings.QUIZ_PAUSE_ADMIN, show_alert=True)
        return
    control = get_control(callback.message.chat.id)
    if control is None or control.stopped:
        await callback.answer(strings.QUIZ_PAUSE_NONE, show_alert=True)
        return
    control.stop()  # unblocks a paused runner; loop exits without a result
    if _is_group(callback.message.chat.type):
        await sync_to_async(abort_active)(callback.message.chat.id)  # mark session ABORTED
    await callback.answer()
    await callback.message.edit_text(strings.QUIZ_STOPPED_MSG)
