import asyncio
import logging

from aiogram import Bot
from aiogram.enums import ParseMode, PollType
from asgiref.sync import sync_to_async

from apps.quiz.services.run import (
    finish_and_leaderboard,
    is_aborted,
    pending_questions,
    prepare_questions,
    record_poll_sent,
)

logger = logging.getLogger(__name__)


async def run_group_quiz(bot: Bot, session_id: int) -> None:
    """Sequentially send quiz polls for a group session, then post the leaderboard."""
    if await sync_to_async(is_aborted)(session_id):
        return  # /stop landed during the ready-check countdown — don't launch
    await sync_to_async(prepare_questions)(session_id)
    questions = await sync_to_async(pending_questions)(session_id)

    total = len(questions)
    for i, question in enumerate(questions, start=1):
        if await sync_to_async(is_aborted)(session_id):
            break
        try:
            msg = await bot.send_poll(
                chat_id=(await sync_to_async(_chat_id)(session_id)),
                question=f"{i}/{total}) {question['prompt']}"[:300],
                options=question["options"],
                type=PollType.QUIZ,
                correct_option_id=question["correct_option"],
                is_anonymous=False,
                open_period=(await sync_to_async(_interval)(session_id)),
                explanation=question["explanation"],
                explanation_parse_mode=ParseMode.HTML,
            )
            await sync_to_async(record_poll_sent)(question["id"], msg.poll.id)
        except Exception as exc:  # keep the quiz resilient to a single bad poll
            logger.warning("group quiz send failed (session %s): %s", session_id, exc)
            continue
        await asyncio.sleep(await sync_to_async(_interval)(session_id))

    chat_id, text = await sync_to_async(finish_and_leaderboard)(session_id)
    await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)


def _chat_id(session_id: int) -> int:
    from apps.quiz.models import GroupQuizSession

    return GroupQuizSession.objects.values_list("chat_id", flat=True).get(id=session_id)


def _interval(session_id: int) -> int:
    from apps.quiz.models import GroupQuizSession

    return GroupQuizSession.objects.values_list("interval_seconds", flat=True).get(id=session_id)
