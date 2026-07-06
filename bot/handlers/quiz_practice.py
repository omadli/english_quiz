import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.learning.services.exam import build_questions
from apps.quiz.services.questions import sample_words
from bot import strings
from bot.handlers.words import _active_books, _book_units
from bot.keyboards.quiz_practice import quiz_books_keyboard, quiz_units_keyboard

logger = logging.getLogger(__name__)
router = Router()

QUIZ_COUNT = 10


def _build_quiz(unit_id: int, count: int) -> list[dict]:
    """Sample up to `count` words from the unit and turn them into quiz questions."""
    words = sample_words([unit_id], count)
    return build_questions(words)


@router.message(F.text == strings.MENU_TEST)
async def menu_test(message: Message) -> None:
    books = await sync_to_async(_active_books)()
    if not books:
        await message.answer(strings.NO_BOOKS)
        return
    await message.answer(strings.QUIZ_PICK_BOOK, reply_markup=quiz_books_keyboard(books))


@router.callback_query(F.data == "pq:books")
async def pq_books(callback: CallbackQuery) -> None:
    await callback.answer()
    books = await sync_to_async(_active_books)()
    await callback.message.edit_text(
        strings.QUIZ_PICK_BOOK, reply_markup=quiz_books_keyboard(books)
    )


@router.callback_query(F.data.startswith("pq:book:"))
async def pq_book(callback: CallbackQuery) -> None:
    await callback.answer()
    book_id = int(callback.data.split(":")[-1])
    units = await sync_to_async(_book_units)(book_id)
    await callback.message.edit_text(
        strings.QUIZ_PICK_UNIT, reply_markup=quiz_units_keyboard(units)
    )


@router.callback_query(F.data.startswith("pq:unit:"))
async def pq_unit(callback: CallbackQuery) -> None:
    await callback.answer()
    unit_id = int(callback.data.split(":")[-1])
    questions = await sync_to_async(_build_quiz)(unit_id, QUIZ_COUNT)
    if not questions:
        await callback.message.edit_text(strings.QUIZ_NO_WORDS)
        return
    await callback.message.edit_text(strings.QUIZ_STARTING.format(count=len(questions)))
    bot = callback.message.bot
    chat_id = callback.message.chat.id
    for q in questions:
        # Native quiz polls give the learner instant right/wrong feedback, so a
        # practice run needs no separate grading. Anonymous → no poll_answer noise.
        await bot.send_poll(
            chat_id=chat_id,
            question=q["prompt"],
            options=q["options"],
            type="quiz",
            correct_option_id=q["correct_option"],
            is_anonymous=True,
            explanation=q["explanation"],
        )
    await bot.send_message(chat_id, strings.QUIZ_DONE)
