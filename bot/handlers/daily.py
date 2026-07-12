from aiogram import F, Router
from aiogram.types import Message
from asgiref.sync import sync_to_async

from apps.accounts.models import User
from apps.learning.services.deliver import (
    _webapp_today_url,
    today_session_payload,
    today_session_words,
)
from apps.learning.services.exam import build_questions
from bot import strings
from bot.handlers.quiz_practice import _countdown_then_run
from bot.sender import _send_daily

router = Router()

_EXAM_TIMER = 30


@router.message(F.text == strings.MENU_TODAY)
async def menu_today(message: Message, user: User) -> None:
    """Re-send today's morning task (word list + one combined audio) on demand."""
    note = await message.answer(strings.TODAY_PREPARING)
    result = await sync_to_async(today_session_payload)(user.id)
    try:
        await note.delete()
    except Exception:
        pass
    if result is None:
        await message.answer(strings.TODAY_NONE)
        return
    caption, audio = result
    await _send_daily(message.bot, message.chat.id, caption, audio, _webapp_today_url())


@router.message(F.text == strings.MENU_EXAM)
async def menu_exam(message: Message, user: User) -> None:
    """A timed quiz over today's task words (reuses the personal-quiz runner)."""
    words = await sync_to_async(today_session_words)(user.id)
    if not words:
        await message.answer(strings.TODAY_NONE)
        return
    questions = await sync_to_async(build_questions)(words, None)
    if not questions:
        await message.answer(strings.QUIZ_NO_WORDS)
        return
    msg = await message.answer(strings.QUIZ_READY_PROMPT)
    await _countdown_then_run(message.bot, message.chat.id, msg.message_id, questions, _EXAM_TIMER)
