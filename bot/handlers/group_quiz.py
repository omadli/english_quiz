import asyncio

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.quiz.models import GroupQuizSession
from apps.quiz.services.session import (
    abort_active,
    get_active_session,
    set_book,
    set_count,
    set_interval,
    start_configuring,
    toggle_type,
    toggle_unit,
)
from bot.keyboards.group_quiz import (
    books_keyboard,
    count_keyboard,
    interval_keyboard,
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


async def is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in ("administrator", "creator")


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
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
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
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
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
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None or not session.unit_ids:
        await callback.answer("Kamida bitta unit tanlang!", show_alert=True)
        return
    await callback.message.edit_text("Savol turlarini tanlang:", reply_markup=types_keyboard([]))


@router.callback_query(F.data.startswith("gq:type:"))
async def toggle_type_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None:
        return
    await sync_to_async(toggle_type)(session, callback.data.split(":")[-1])
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    await callback.message.edit_reply_markup(reply_markup=types_keyboard(session.question_types))


@router.callback_query(F.data == "gq:types_done")
async def types_done(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None or not session.question_types:
        await callback.answer("Kamida bitta tur tanlang!", show_alert=True)
        return
    await callback.message.edit_text("Nechta savol?", reply_markup=count_keyboard())


@router.callback_query(F.data.startswith("gq:count:"))
async def pick_count(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None:
        return
    await sync_to_async(set_count)(session, int(callback.data.split(":")[-1]))
    await callback.message.edit_text(
        "Har savol uchun necha soniya?", reply_markup=interval_keyboard()
    )


@router.callback_query(F.data.startswith("gq:int:"))
async def pick_interval(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None:
        return
    await sync_to_async(set_interval)(session, int(callback.data.split(":")[-1]))
    await callback.message.edit_text(
        "Tayyor! Boshlash uchun bosing 👇", reply_markup=start_keyboard()
    )


@router.callback_query(F.data == "gq:start")
async def start_quiz(callback: CallbackQuery) -> None:
    await callback.answer()
    session = await sync_to_async(get_active_session)(callback.message.chat.id)
    if session is None:
        return
    await callback.message.delete()
    asyncio.create_task(run_group_quiz(callback.bot, session.id))


@router.message(Command("stop"))
async def cmd_stop(message: Message) -> None:
    if not await is_chat_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer(_NOT_ADMIN)
        return
    stopped = await sync_to_async(abort_active)(message.chat.id)
    await message.answer("To'xtatildi!" if stopped else "To'xtatiladigan test yo'q.")
