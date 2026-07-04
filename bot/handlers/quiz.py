from aiogram import Router
from aiogram.types import PollAnswer
from asgiref.sync import sync_to_async

from apps.learning.services.exam_grade import record_answer

router = Router()


@router.poll_answer()
async def on_poll_answer(poll_answer: PollAnswer) -> None:
    await sync_to_async(record_answer)(poll_answer.poll_id, poll_answer.option_ids)
