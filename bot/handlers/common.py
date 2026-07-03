import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, Message

from bot import strings

logger = logging.getLogger("bot")
router = Router()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(strings.HELP_TEXT)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(strings.NOTHING_TO_CANCEL)
        return
    await state.clear()
    await message.answer(strings.CANCELLED)


@router.error()
async def on_error(event: ErrorEvent) -> None:
    logger.exception("Bot handler error", exc_info=event.exception)
    message = getattr(event.update, "message", None) or getattr(
        getattr(event.update, "callback_query", None), "message", None
    )
    if message is not None:
        await message.answer(strings.GENERIC_ERROR)
