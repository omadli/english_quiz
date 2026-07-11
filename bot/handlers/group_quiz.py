import asyncio
import html

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.catalog.models import Unit
from apps.quiz.models import GroupQuizSession
from apps.quiz.services.session import (
    abort_active,
    create_group_session_from_config,
    get_active_session,
    set_book,
    set_count,
    set_interval,
    start_configuring,
    toggle_type,
    toggle_unit,
)
from bot import strings
from bot.keyboards.group_quiz import (
    books_keyboard,
    count_keyboard,
    interval_keyboard,
    ready_keyboard,
    start_keyboard,
    types_keyboard,
    units_keyboard,
)
from bot.runner_group_quiz import run_group_quiz

router = Router()

_ASK_BOOK = "📚 Qaysi kitobdan test qilamiz?"
_ASK_UNITS = "Unit(lar)ni tanlang, so'ng «Tayyor» bosing."
_NOT_ADMIN = "Bu buyruq faqat guruh adminlari uchun."
_ALREADY = "Bu guruhda test allaqachon sozlanmoqda yoki ketmoqda. /stop bilan to'xtating."
_NOT_OWNER = "Bu testni faqat uni boshlagan admin boshqaradi."
_READY_CHECK = "🎯 <b>Test tayyor!</b>\nQatnashaman deganlar «✅ Men tayyorman» bosing 👇"
_READY_LIST = "\n\n✅ Tayyor ({n}): {names}"
_CONFIGURING = "⚙️ Sozlanmoqda..."
_NO_ONE_READY = "Hali hech kim tayyor emas 🤷"

# ponytail: in-memory ready-check registry — one polling bot process, like
# quiz_practice._pending. Move to a GroupQuizSession field if you run replicas.
_ready: dict[int, dict[int, str]] = {}  # session_id -> {user_id: display_name}


def _config_text(session: GroupQuizSession) -> str:
    """Config summary shown in the ready-check: book · units · count · time · types."""
    book = session.book.title if session.book_id else "—"
    numbers = list(
        Unit.objects.filter(pk__in=session.unit_ids)
        .order_by("number")
        .values_list("number", flat=True)
    )
    types = ", ".join(strings.QUIZ_TYPE_LABELS.get(t, t) for t in session.question_types)
    return (
        f"📚 <b>{html.escape(book)}</b>\n"
        f"🗂 Bo'limlar: <b>{', '.join(map(str, numbers)) or '—'}</b>\n"
        f"✏️ <b>{session.question_count} ta savol</b> · "
        f"⏱ <b>{session.interval_seconds} soniya</b>\n"
        f"🎲 <b>{types or '—'}</b>"
    )


def _ready_text(config: str, names: list[str]) -> str:
    text = f"{_READY_CHECK}\n\n{config}"
    if names:
        joined = ", ".join(html.escape(n) for n in names)
        text += _READY_LIST.format(n=len(names), names=joined)
    return text


async def seed_group_quiz_from_config(bot: Bot, chat_id: int, user_id: int, config: dict) -> None:
    """`?startgroup=<code>` landed in a group → seed the session and open the ready-check."""
    session = await sync_to_async(create_group_session_from_config)(chat_id, user_id, config)
    if session is None:
        await bot.send_message(chat_id, _ALREADY)
        return
    _ready[session.id] = {}
    config = await sync_to_async(_config_text)(session)
    await bot.send_message(chat_id, _ready_text(config, []), reply_markup=ready_keyboard(0))


async def is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")


async def _owned_session(callback: CallbackQuery) -> GroupQuizSession | None:
    """Fetch the active session and enforce that only its starter controls it.

    Every wizard callback shares this check so a non-admin group member
    tapping a live inline keyboard (or racing the admin) can't hijack the
    config or launch the quiz. Mirrors `get_active_session` returning
    ``None`` when there's nothing to act on, but additionally answers the
    callback with an alert when the tapper isn't the session's starter.
    """
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None:
        return None
    if session.started_by_telegram_id != callback.from_user.id:
        await callback.answer(_NOT_OWNER, show_alert=True)
        return None
    return session


@router.message(Command("quiz"))
async def cmd_quiz(message: Message) -> None:
    if not await is_chat_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer(_NOT_ADMIN)
        return
    session = await sync_to_async(start_configuring)(message.chat.id, message.from_user.id)
    if session is None:
        await message.answer(_ALREADY)
        return
    await message.answer(_ASK_BOOK, reply_markup=books_keyboard())


@router.callback_query(F.data.startswith("gq:book:"))
async def pick_book(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await _owned_session(callback)
    if session is None:
        return
    book_number = int(callback.data.split(":")[-1])
    await sync_to_async(set_book)(session, book_number)
    markup = await sync_to_async(units_keyboard)(book_number, [])
    await callback.message.edit_text(_ASK_UNITS, reply_markup=markup)


def _book_number(session: GroupQuizSession) -> int | None:
    """Read the related book's number without leaking a lazy FK fetch into async code.

    ``session.book`` is a lazy relation: if it isn't already cached, touching it
    fires a real query. Doing that directly inside an `async def` (as opposed to
    behind `sync_to_async`) raises `SynchronousOnlyOperation` under a real event
    loop, so this helper keeps that access on the sync side.
    """
    return session.book.number if session.book_id else None


@router.callback_query(F.data.startswith("gq:unit:"))
async def toggle_unit_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await _owned_session(callback)
    if session is None or await sync_to_async(_book_number)(session) is None:
        return
    unit_id = int(callback.data.split(":")[-1])
    await sync_to_async(toggle_unit)(session, unit_id)
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    book_number = await sync_to_async(_book_number)(session)
    markup = await sync_to_async(units_keyboard)(book_number, session.unit_ids)
    await callback.message.edit_reply_markup(reply_markup=markup)


@router.callback_query(F.data == "gq:units_done")
async def units_done(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await _owned_session(callback)
    if session is None or not session.unit_ids:
        await callback.answer("Kamida bitta unit tanlang!", show_alert=True)
        return
    await callback.message.edit_text("Savol turlarini tanlang:", reply_markup=types_keyboard([]))


@router.callback_query(F.data.startswith("gq:type:"))
async def toggle_type_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await _owned_session(callback)
    if session is None:
        return
    await sync_to_async(toggle_type)(session, callback.data.split(":")[-1])
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    await callback.message.edit_reply_markup(reply_markup=types_keyboard(session.question_types))


@router.callback_query(F.data == "gq:types_done")
async def types_done(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await _owned_session(callback)
    if session is None or not session.question_types:
        await callback.answer("Kamida bitta tur tanlang!", show_alert=True)
        return
    await callback.message.edit_text("Nechta savol?", reply_markup=count_keyboard())


@router.callback_query(F.data.startswith("gq:count:"))
async def pick_count(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await _owned_session(callback)
    if session is None:
        return
    await sync_to_async(set_count)(session, int(callback.data.split(":")[-1]))
    await callback.message.edit_text(
        "Har savol uchun necha soniya?", reply_markup=interval_keyboard()
    )


@router.callback_query(F.data.startswith("gq:int:"))
async def pick_interval(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await _owned_session(callback)
    if session is None:
        return
    await sync_to_async(set_interval)(session, int(callback.data.split(":")[-1]))
    await callback.message.edit_text(
        "Tayyor! Boshlash uchun bosing 👇", reply_markup=start_keyboard()
    )


@router.callback_query(F.data == "gq:start")
async def start_quiz(callback: CallbackQuery) -> None:
    """Owner finished config → open the ready-check (no launch yet)."""
    await callback.answer()
    session = await _owned_session(callback)
    if session is None:
        return
    _ready[session.id] = {}
    config = await sync_to_async(_config_text)(session)
    await callback.message.edit_text(
        _ready_text(config, []), reply_markup=ready_keyboard(0), parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data == "gq:ready")
async def toggle_ready(callback: CallbackQuery) -> None:
    """Any group member marks themselves ready (or un-ready)."""
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None:
        await callback.answer()
        return
    readies = _ready.setdefault(session.id, {})
    if callback.from_user.id in readies:
        del readies[callback.from_user.id]
        await callback.answer("Bekor qilindi")
    else:
        readies[callback.from_user.id] = callback.from_user.full_name
        await callback.answer("Tayyor! ✅")
    names = list(readies.values())
    config = await sync_to_async(_config_text)(session)
    try:
        await callback.message.edit_text(
            _ready_text(config, names), reply_markup=ready_keyboard(len(names)),
            parse_mode=ParseMode.HTML,
        )
    except Exception:  # "message is not modified" / message gone
        pass


@router.callback_query(F.data == "gq:go")
async def go_quiz(callback: CallbackQuery) -> None:
    """Owner launches: needs ≥1 ready person, then countdown → run."""
    session = await _owned_session(callback)
    if session is None:
        return
    if not _ready.get(session.id):
        await callback.answer(_NO_ONE_READY, show_alert=True)
        return
    await callback.answer()
    _ready.pop(session.id, None)
    asyncio.create_task(
        _countdown_then_run(
            callback.bot, session.id, callback.message.chat.id, callback.message.message_id
        )
    )


async def _countdown_then_run(bot: Bot, session_id: int, chat_id: int, message_id: int) -> None:
    for text in (_CONFIGURING, "3️⃣", "2️⃣", "1️⃣"):
        try:
            await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)
        except Exception:  # message may be gone; keep counting down
            pass
        await asyncio.sleep(1)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass
    await run_group_quiz(bot, session_id)


@router.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    if not await is_chat_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer(_NOT_ADMIN)
        return
    stopped = await sync_to_async(abort_active)(message.chat.id)
    await message.answer("To'xtatildi!" if stopped else "To'xtatiladigan test yo'q.")
