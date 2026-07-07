from aiogram import Router
from aiogram.types import PollAnswer
from asgiref.sync import sync_to_async

from apps.learning.services.exam_grade import record_answer
from apps.quiz.services.scoring import record_group_answer
from bot.handlers.quiz_practice import register_answer

router = Router()


@router.poll_answer()
async def on_poll_answer(poll_answer: PollAnswer) -> None:
    if register_answer(poll_answer.poll_id, poll_answer.option_ids):
        return  # a personal practice-quiz answer — handled by its runner
    handled = await sync_to_async(record_group_answer)(
        poll_answer.poll_id,
        poll_answer.option_ids,
        poll_answer.user.id,
        poll_answer.user.username or "",
        poll_answer.user.full_name,
    )
    if not handled:
        await sync_to_async(record_answer)(poll_answer.poll_id, poll_answer.option_ids)
