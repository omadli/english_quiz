import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.enums import PollType
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.learning.services.exam import build_questions
from apps.quiz.services.questions import sample_words
from bot import strings
from bot.handlers.words import _active_books, _book_units
from bot.keyboards.quiz_practice import quiz_books_keyboard, quiz_units_keyboard
from bot.states.quiz import QuizStates

logger = logging.getLogger(__name__)
router = Router()

QUIZ_COUNT = 10
QUIZ_TIMER = 30  # seconds per question

# ponytail: in-memory poll registry — fine for one polling bot process. If you
# run multiple bot workers / webhook replicas, move this to Redis.
_pending: dict[str, dict] = {}


def register_answer(poll_id: str, option_ids: list[int]) -> bool:
    """Called from the poll-answer handler; wakes a waiting personal-quiz runner.
    Returns True if this poll belongs to a running personal quiz."""
    entry = _pending.get(poll_id)
    if entry is None:
        return False
    entry["chosen"] = option_ids[0] if option_ids else None
    entry["event"].set()
    return True


def _build_quiz(unit_ids: list[int], count: int) -> list[dict]:
    return build_questions(sample_words(unit_ids, count))


@router.message(F.text == strings.MENU_TEST)
async def menu_test(message: Message, state: FSMContext) -> None:
    await state.clear()
    books = await sync_to_async(_active_books)()
    if not books:
        await message.answer(strings.NO_BOOKS)
        return
    await message.answer(strings.QUIZ_PICK_BOOK, reply_markup=quiz_books_keyboard(books))


@router.callback_query(F.data == "pq:books")
async def pq_books(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    books = await sync_to_async(_active_books)()
    await callback.message.edit_text(
        strings.QUIZ_PICK_BOOK, reply_markup=quiz_books_keyboard(books)
    )


@router.callback_query(F.data.startswith("pq:book:"))
async def pq_book(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    book_id = int(callback.data.split(":")[-1])
    units = await sync_to_async(_book_units)(book_id)
    await state.set_state(QuizStates.units)
    await state.update_data(book_id=book_id, sel=[])
    await callback.message.edit_text(
        strings.QUIZ_PICK_UNIT, reply_markup=quiz_units_keyboard(units, set())
    )


@router.callback_query(QuizStates.units, F.data.startswith("pq:u:"))
async def pq_toggle_unit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    uid = int(callback.data.split(":")[-1])
    data = await state.get_data()
    sel = set(data.get("sel", []))
    sel.discard(uid) if uid in sel else sel.add(uid)
    await state.update_data(sel=list(sel))
    units = await sync_to_async(_book_units)(data["book_id"])
    await callback.message.edit_reply_markup(reply_markup=quiz_units_keyboard(units, sel))


@router.callback_query(QuizStates.units, F.data == "pq:all")
async def pq_all(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    units = await sync_to_async(_book_units)(data["book_id"])
    sel = {u.pk for u in units}
    await state.update_data(sel=list(sel))
    await callback.message.edit_reply_markup(reply_markup=quiz_units_keyboard(units, sel))


@router.callback_query(QuizStates.units, F.data == "pq:go")
async def pq_go(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    sel = data.get("sel", [])
    if not sel:
        await callback.answer(strings.QUIZ_PICK_UNIT_EMPTY, show_alert=True)
        return
    await callback.answer()
    await state.clear()
    questions = await sync_to_async(_build_quiz)(sel, QUIZ_COUNT)
    if not questions:
        await callback.message.edit_text(strings.QUIZ_NO_WORDS)
        return
    await callback.message.edit_text(strings.QUIZ_STARTING.format(count=len(questions)))
    asyncio.create_task(
        run_personal_quiz(callback.message.bot, callback.message.chat.id, questions)
    )


async def run_personal_quiz(bot: Bot, chat_id: int, questions: list[dict]) -> None:
    """QuizBot-style: one 30s poll at a time; advance on answer, mark skips on
    timeout, pause after 2 consecutive skips."""
    correct = 0
    skips = 0
    for question in questions:
        event = asyncio.Event()
        try:
            msg = await bot.send_poll(
                chat_id=chat_id,
                question=question["prompt"],
                options=question["options"],
                type=PollType.QUIZ,
                correct_option_id=question["correct_option"],
                is_anonymous=False,
                open_period=QUIZ_TIMER,
                explanation=question["explanation"],
            )
        except Exception as exc:  # keep the quiz resilient to a single bad poll
            logger.warning("personal quiz poll failed (chat %s): %s", chat_id, exc)
            continue
        poll_id = msg.poll.id
        _pending[poll_id] = {"event": event, "chosen": None}
        try:
            await asyncio.wait_for(event.wait(), timeout=QUIZ_TIMER + 2)
            skips = 0
            if _pending[poll_id]["chosen"] == question["correct_option"]:
                correct += 1
        except TimeoutError:
            skips += 1
            await bot.send_message(chat_id, strings.QUIZ_SKIPPED)
            if skips >= 2:
                await bot.send_message(chat_id, strings.QUIZ_PAUSED)
                _pending.pop(poll_id, None)
                return
        finally:
            _pending.pop(poll_id, None)
    await bot.send_message(
        chat_id, strings.QUIZ_RESULT.format(correct=correct, total=len(questions))
    )
