import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.learning.services.book_pdf import active_books, get_book_document
from bot import strings
from bot.keyboards.books import books_keyboard
from bot.sender import send_document

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("book"))
async def cmd_book(message: Message) -> None:
    books = await sync_to_async(active_books)()
    if not books:
        await message.answer(strings.NO_BOOKS)
        return
    await message.answer(strings.PICK_BOOK_PDF, reply_markup=books_keyboard(books))


@router.callback_query(F.data.startswith("pdf:book:"))
async def send_pdf(callback: CallbackQuery) -> None:
    await callback.answer(strings.PDF_SENDING)
    book_id = int(callback.data.split(":")[-1])
    doc = await sync_to_async(get_book_document)(book_id)
    if doc is None:
        await callback.message.answer(strings.PDF_NOT_AVAILABLE)
        return
    filename, data = doc
    try:
        await sync_to_async(send_document)(callback.message.chat.id, data, filename)
    except Exception as exc:  # best-effort
        logger.warning("failed to send book pdf %s: %s", book_id, exc)
        await callback.message.answer(strings.PDF_ERROR)
