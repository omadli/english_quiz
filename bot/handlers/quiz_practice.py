import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.enums import PollType
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)
from asgiref.sync import sync_to_async
from django.conf import settings as dj_settings

from apps.catalog.models import Book, Unit
from apps.learning.services.exam import build_questions
from apps.quiz.services.questions import sample_words
from apps.quiz.services.share import recent_shared_quizzes, save_shared_quiz
from bot import strings
from bot.handlers.words import _active_books, _book_units
from bot.keyboards.quiz_practice import (
    quiz_books_keyboard,
    quiz_count_keyboard,
    quiz_summary_keyboard,
    quiz_time_keyboard,
    quiz_types_keyboard,
    quiz_units_keyboard,
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


def _summary_data(book_id: int, unit_ids: list[int]) -> tuple[str, list[int]]:
    book = Book.objects.filter(pk=book_id).first()
    numbers = list(
        Unit.objects.filter(pk__in=unit_ids).order_by("number").values_list("number", flat=True)
    )
    return (book.title if book else "", numbers)


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
    book_title, numbers = await sync_to_async(_summary_data)(data["book_id"], data["sel"])
    text = strings.QUIZ_SUMMARY.format(
        book=book_title,
        units=", ".join(map(str, numbers)),
        count=data.get("count", QUIZ_COUNT),
        time=data.get("interval", QUIZ_TIMER),
        types=", ".join(strings.QUIZ_TYPE_LABELS[t] for t in types),
    )
    await callback.message.edit_text(
        text, reply_markup=quiz_summary_keyboard(bool(dj_settings.BOT_USERNAME))
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


def _share_button(username: str, quiz_id: int) -> InlineKeyboardMarkup:
    deep_link = f"https://t.me/{username}?start=quiz_{quiz_id}"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=strings.BTN_START_SHARED, url=deep_link)
    ]])


async def _ensure_shared(state: FSMContext, user_id: int) -> int:
    """Persist the wizard's config as a SharedQuiz once, reusing it for share+group."""
    data = await state.get_data()
    if data.get("shared_id"):
        return data["shared_id"]
    quiz = await sync_to_async(save_shared_quiz)(
        user_id,
        data.get("book_id"),
        data.get("sel", []),
        data.get("count", QUIZ_COUNT),
        data.get("interval", QUIZ_TIMER),
        data.get("types"),
    )
    await state.update_data(shared_id=quiz.id)
    return quiz.id


@router.callback_query(QuizStates.summary, F.data == "pq:share")
async def pq_share(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    username = dj_settings.BOT_USERNAME
    if not username:
        await callback.message.answer(strings.SHARE_NO_USERNAME)
        return
    quiz_id = await _ensure_shared(state, callback.from_user.id)
    # Forwardable message (URL buttons survive forwarding) + inline hint.
    await callback.message.answer(strings.SHARE_TEXT, reply_markup=_share_button(username, quiz_id))
    await callback.message.answer(strings.SHARE_INLINE_HINT.format(username=username))


@router.callback_query(QuizStates.summary, F.data == "pq:group")
async def pq_group(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    username = dj_settings.BOT_USERNAME
    if not username:
        await callback.message.answer(strings.SHARE_NO_USERNAME)
        return
    quiz_id = await _ensure_shared(state, callback.from_user.id)
    url = f"https://t.me/{username}?startgroup=quiz_{quiz_id}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=strings.BTN_PICK_GROUP, url=url)
    ]])
    await callback.message.answer(strings.GROUP_PICK_HINT, reply_markup=kb)


@router.inline_query()
async def inline_share(query: InlineQuery) -> None:
    """`@bot ...` in any chat → insert one of the user's own shared tests."""
    username = dj_settings.BOT_USERNAME
    cards = await sync_to_async(recent_shared_quizzes)(query.from_user.id) if username else []
    if cards:
        results = [
            InlineQueryResultArticle(
                id=str(c["id"]),
                title=c["title"],
                description=c["desc"],
                input_message_content=InputTextMessageContent(message_text=strings.SHARE_TEXT),
                reply_markup=_share_button(username, c["id"]),
            )
            for c in cards
        ]
    else:
        results = [
            InlineQueryResultArticle(
                id="none",
                title=strings.INLINE_NONE_TITLE,
                description=strings.INLINE_NONE_DESC,
                input_message_content=InputTextMessageContent(message_text=strings.INLINE_NONE_MSG),
            )
        ]
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
                open_period=timer,
                explanation=question["explanation"],
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
                return
        finally:
            _pending.pop(poll_id, None)
    await bot.send_message(
        chat_id, strings.QUIZ_RESULT.format(correct=correct, total=len(questions))
    )
