import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode, PollType
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)
from asgiref.sync import sync_to_async
from django.conf import settings as dj_settings

from apps.catalog.models import Book, Unit
from apps.learning.services.exam import build_questions
from apps.learning.services.progress import mark_words_learned
from apps.quiz.services.questions import sample_words
from apps.quiz.services.quiz_code import MAX_LEN, card_for, encode_quiz
from apps.quiz.services.share import save_shared_quiz
from bot import strings
from bot.handlers.words import _active_books, _book_units
from bot.keyboards.quiz_practice import (
    quiz_books_keyboard,
    quiz_count_keyboard,
    quiz_summary_keyboard,
    quiz_time_keyboard,
    quiz_types_keyboard,
    quiz_units_keyboard,
    shared_card_keyboard,
)
from bot.states.quiz import QuizStates

logger = logging.getLogger(__name__)
router = Router()

QUIZ_COUNT = 10
QUIZ_TIMER = 30

# ponytail: in-memory poll registry — fine for one polling bot process. Move to
# Redis if you run multiple bot workers / webhook replicas.
_pending: dict[str, dict] = {}


def register_answer(poll_id: str, option_ids: list[int]) -> bool:
    entry = _pending.get(poll_id)
    if entry is None:
        return False
    entry["chosen"] = option_ids[0] if option_ids else None
    entry["event"].set()
    return True


def _build_quiz(unit_ids: list[int], count: int, types: list[str] | None) -> list[dict]:
    return build_questions(sample_words(unit_ids, count), types=types or None)


def _summary_and_code(
    book_id: int, unit_ids: list[int], count: int, interval: int, types: list[str], tg_id: int
) -> tuple[str, list[int], str]:
    """Summary display + the self-contained share code (DB fallback on overflow)."""
    book = Book.objects.filter(pk=book_id).first()
    numbers = list(
        Unit.objects.filter(pk__in=unit_ids).order_by("number").values_list("number", flat=True)
    )
    code = encode_quiz(book.number if book else 0, numbers, count, interval, types)
    if len(code) > MAX_LEN:  # rare scattered selection → q<pk> token backed by SharedQuiz
        sq = save_shared_quiz(tg_id, book_id, unit_ids, count, interval, types)
        code = f"q{sq.id}"
    return (book.title if book else "", numbers, code)


# ---- step 1: book -----------------------------------------------------------
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


# ---- step 2: units (multiselect) --------------------------------------------
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


@router.callback_query(QuizStates.units, F.data == "pq:next")
async def pq_next(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("sel"):
        await callback.answer(strings.QUIZ_PICK_UNIT_EMPTY, show_alert=True)
        return
    await callback.answer()
    await state.set_state(QuizStates.count)
    await callback.message.edit_text(strings.QUIZ_PICK_COUNT, reply_markup=quiz_count_keyboard())


# ---- step 3: count ----------------------------------------------------------
@router.callback_query(QuizStates.count, F.data.startswith("pq:count:"))
async def pq_count(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(count=int(callback.data.split(":")[-1]))
    await state.set_state(QuizStates.time)
    await callback.message.edit_text(strings.QUIZ_PICK_TIME, reply_markup=quiz_time_keyboard())


# ---- step 4: time -----------------------------------------------------------
@router.callback_query(QuizStates.time, F.data.startswith("pq:time:"))
async def pq_time(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(interval=int(callback.data.split(":")[-1]))
    await state.set_state(QuizStates.types)
    await callback.message.edit_text(
        strings.QUIZ_PICK_TYPES, reply_markup=quiz_types_keyboard(set())
    )


# ---- step 5: types (multiselect) --------------------------------------------
@router.callback_query(QuizStates.types, F.data.startswith("pq:type:"))
async def pq_type(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    code = callback.data.split(":")[-1]
    data = await state.get_data()
    types = set(data.get("types", []))
    types.discard(code) if code in types else types.add(code)
    await state.update_data(types=list(types))
    await callback.message.edit_reply_markup(reply_markup=quiz_types_keyboard(types))


@router.callback_query(QuizStates.types, F.data == "pq:types_done")
async def pq_types_done(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    types = data.get("types") or list(strings.QUIZ_TYPE_LABELS.keys())  # default: all
    await state.update_data(types=types)
    await state.set_state(QuizStates.summary)
    count = data.get("count", QUIZ_COUNT)
    interval = data.get("interval", QUIZ_TIMER)
    book_title, numbers, code = await sync_to_async(_summary_and_code)(
        data["book_id"], data["sel"], count, interval, types, callback.from_user.id
    )
    await state.update_data(code=code)
    text = strings.QUIZ_SUMMARY.format(
        book=book_title,
        units=", ".join(map(str, numbers)),
        count=count,
        time=interval,
        types=", ".join(strings.QUIZ_TYPE_LABELS[t] for t in types),
    )
    await callback.message.edit_text(
        text, reply_markup=quiz_summary_keyboard(code, dj_settings.BOT_USERNAME or None)
    )


# ---- summary actions --------------------------------------------------------
@router.callback_query(QuizStates.summary, F.data == "pq:start")
async def pq_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    questions = await sync_to_async(_build_quiz)(
        data["sel"], data.get("count", QUIZ_COUNT), data.get("types")
    )
    timer = data.get("interval", QUIZ_TIMER)
    await state.clear()
    if not questions:
        await callback.message.edit_text(strings.QUIZ_NO_WORDS)
        return
    asyncio.create_task(
        _countdown_then_run(
            callback.message.bot, callback.message.chat.id, callback.message.message_id,
            questions, timer,
        )
    )


@router.inline_query()
async def inline_share(query: InlineQuery) -> None:
    """Share a test via inline: the query IS the self-contained code (from the
    «🔗 Testni ulashish» switch_inline button). Inserts a card whose buttons
    start the test personally, in a group, or re-share it."""
    username = dj_settings.BOT_USERNAME
    code = (query.query or "").strip()
    card = await sync_to_async(card_for)(code) if (username and code) else None
    if card is None:
        results = [InlineQueryResultArticle(
            id="none",
            title=strings.INLINE_NONE_TITLE,
            description=strings.INLINE_NONE_DESC,
            input_message_content=InputTextMessageContent(message_text=strings.INLINE_NONE_MSG),
        )]
    else:
        text = strings.QUIZ_SUMMARY.format(
            book=card["book"], units=card["units"], count=card["count"],
            time=card["interval"],
            types=", ".join(strings.QUIZ_TYPE_LABELS[t] for t in card["types"]),
        )
        results = [InlineQueryResultArticle(
            id=code,
            title=f"🧠 {card['book']}",
            description=(
                f"🗂 Bo'limlar: {card['units']} · "
                f"{card['count']} ta savol · ⏱ {card['interval']}s"
            ),
            input_message_content=InputTextMessageContent(
                message_text=text, parse_mode=ParseMode.HTML
            ),
            reply_markup=shared_card_keyboard(code, username),
        )]
    await query.answer(results, cache_time=1, is_personal=True)


async def start_shared_quiz(
    bot: Bot, chat_id: int, unit_ids: list[int], count: int, interval: int, types: list[str] | None
) -> None:
    """Launch a shared test in `chat_id` (used by the `quiz_<id>` deep link)."""
    questions = await sync_to_async(_build_quiz)(unit_ids, count, types or None)
    if not questions:
        await bot.send_message(chat_id, strings.QUIZ_NO_WORDS)
        return
    msg = await bot.send_message(chat_id, strings.QUIZ_READY_PROMPT)
    await _countdown_then_run(bot, chat_id, msg.message_id, questions, interval)


# ---- runner -----------------------------------------------------------------
async def _countdown_then_run(
    bot: Bot, chat_id: int, message_id: int, questions: list[dict], timer: int
) -> None:
    for text in (strings.QUIZ_READY_PROMPT, "3️⃣", "2️⃣", "1️⃣"):
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)
        except Exception:  # message may be gone; keep counting down
            pass
        await asyncio.sleep(1)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    await run_personal_quiz(bot, chat_id, questions, timer)


async def run_personal_quiz(
    bot: Bot, chat_id: int, questions: list[dict], timer: int = QUIZ_TIMER
) -> None:
    """QuizBot-style: one poll at a time (open_period=timer); advance on answer,
    mark skips on timeout, pause after 2 consecutive skips."""
    from bot.quiz_control import clear_control, new_control

    control = new_control(chat_id)
    try:
        correct = await _run_personal_loop(bot, chat_id, questions, timer, control)
    finally:
        clear_control(chat_id)
    if correct is None:  # /stop pressed → no result summary
        return
    await bot.send_message(
        chat_id, strings.QUIZ_RESULT.format(correct=correct, total=len(questions))
    )
    # Completing the test is the ONLY way its words become 'learned' (no manual marking).
    word_ids = [q["word"].id for q in questions if q.get("word")]
    marked = await sync_to_async(mark_words_learned)(chat_id, word_ids)
    if marked:
        await bot.send_message(chat_id, strings.QUIZ_LEARNED_MARKED.format(n=marked))


async def _run_personal_loop(bot, chat_id, questions, timer, control) -> int | None:
    """The poll loop. Returns the correct count, or None if the user hit /stop."""
    correct = 0
    skips = 0
    total = len(questions)
    for i, question in enumerate(questions, start=1):
        if not await control.gate():  # blocks while paused; False → stopped
            return None
        event = asyncio.Event()
        try:
            msg = await bot.send_poll(
                chat_id=chat_id,
                question=f"{i}/{total}) {question['prompt']}"[:300],
                options=question["options"],
                type=PollType.QUIZ,
                correct_option_id=question["correct_option"],
                is_anonymous=False,
                open_period=timer,
                explanation=question["explanation"],
                explanation_parse_mode=ParseMode.HTML,
            )
        except Exception as exc:
            logger.warning("personal quiz poll failed (chat %s): %s", chat_id, exc)
            continue
        poll_id = msg.poll.id
        _pending[poll_id] = {"event": event, "chosen": None}
        try:
            await asyncio.wait_for(event.wait(), timeout=timer + 2)
            skips = 0
            if _pending[poll_id]["chosen"] == question["correct_option"]:
                correct += 1
        except TimeoutError:
            skips += 1
            await bot.send_message(chat_id, strings.QUIZ_SKIPPED)
            if skips >= 2:
                await bot.send_message(chat_id, strings.QUIZ_PAUSED)
                _pending.pop(poll_id, None)
                return None
        finally:
            _pending.pop(poll_id, None)
    return correct
