from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async
from django.utils.html import escape, strip_tags

from apps.catalog.models import Book, Unit, Word
from bot import strings
from bot.keyboards.words import (
    words_back_keyboard,
    words_books_keyboard,
    words_units_keyboard,
)

router = Router()


def _active_books() -> list[Book]:
    return list(Book.objects.filter(is_active=True).order_by("number"))


def _book_units(book_id: int) -> list[Unit]:
    return list(Unit.objects.filter(book_id=book_id).order_by("number"))


def _unit_with_words(unit_id: int) -> tuple[Unit, list[Word]] | None:
    unit = Unit.objects.select_related("book").filter(pk=unit_id).first()
    if unit is None:
        return None
    return unit, list(Word.objects.filter(unit_id=unit_id).order_by("order"))


def format_words(unit: Unit, words: list[Word]) -> str:
    lines = [strings.WORDS_HEADER.format(book=unit.book.title, unit=unit.number)]
    for i, w in enumerate(words, start=1):
        pos = f"  <i>{w.part_of_speech}</i>" if w.part_of_speech else ""
        lines.append(f"{i}. <b>{w.en}</b> — {w.uz or '—'}{pos}")
    return "\n".join(lines)


@router.message(F.text == strings.MENU_WORDS)
async def menu_words(message: Message) -> None:
    books = await sync_to_async(_active_books)()
    if not books:
        await message.answer(strings.NO_BOOKS)
        return
    await message.answer(strings.WORDS_PICK_BOOK, reply_markup=words_books_keyboard(books))


@router.callback_query(F.data == "wl:books")
async def wl_books(callback: CallbackQuery) -> None:
    await callback.answer()
    books = await sync_to_async(_active_books)()
    await callback.message.edit_text(
        strings.WORDS_PICK_BOOK, reply_markup=words_books_keyboard(books)
    )


@router.callback_query(F.data.startswith("wl:book:"))
async def wl_book(callback: CallbackQuery) -> None:
    await callback.answer()
    book_id = int(callback.data.split(":")[-1])
    units = await sync_to_async(_book_units)(book_id)
    await callback.message.edit_text(
        strings.WORDS_PICK_UNIT, reply_markup=words_units_keyboard(units)
    )


@router.callback_query(F.data.startswith("wl:units:"))
async def wl_units(callback: CallbackQuery) -> None:
    await callback.answer()
    book_id = int(callback.data.split(":")[-1])
    units = await sync_to_async(_book_units)(book_id)
    await callback.message.edit_text(
        strings.WORDS_PICK_UNIT, reply_markup=words_units_keyboard(units)
    )


@router.callback_query(F.data.startswith("wl:unit:"))
async def wl_unit(callback: CallbackQuery) -> None:
    await callback.answer()
    unit_id = int(callback.data.split(":")[-1])
    result = await sync_to_async(_unit_with_words)(unit_id)
    if result is None:
        return
    unit, words = result
    if not words:
        await callback.message.edit_text(
            strings.WORDS_EMPTY, reply_markup=words_back_keyboard(unit.book_id, unit.pk)
        )
        return
    await callback.message.edit_text(
        format_words(unit, words), reply_markup=words_back_keyboard(unit.book_id, unit.pk)
    )


def _detail_block(index: int, w: Word) -> str:
    ipa = f" <code>{escape(w.pronunciation)}</code>" if w.pronunciation else ""
    pos = f" <i>({escape(w.part_of_speech)})</i>" if w.part_of_speech else ""
    parts = [f"{index}) <b>{escape(w.en)}</b>{ipa}{pos} — <b>{escape(w.uz) or '—'}</b>"]
    if w.definition:
        parts.append(f"<blockquote>{escape(w.definition)}</blockquote>")
    if w.example:
        parts.append(f"<i>{escape(strip_tags(w.example))}</i>")
    return "\n".join(parts)


def _pack(header: str, blocks: list[str], limit: int = 3900) -> list[str]:
    """Greedily pack blocks into <= limit-char messages (Telegram caps at 4096)."""
    messages, current = [], header
    for block in blocks:
        if len(current) + len(block) + 2 > limit:
            messages.append(current)
            current = block
        else:
            current += ("\n\n" if current else "") + block
    if current:
        messages.append(current)
    return messages


@router.callback_query(F.data.startswith("wl:detail:"))
async def wl_detail(callback: CallbackQuery) -> None:
    await callback.answer()
    unit_id = int(callback.data.split(":")[-1])
    result = await sync_to_async(_unit_with_words)(unit_id)
    if result is None:
        return
    unit, words = result
    if not words:
        await callback.message.answer(strings.WORDS_EMPTY)
        return
    header = strings.WORDS_HEADER.format(book=unit.book.title, unit=unit.number)
    blocks = [_detail_block(i, w) for i, w in enumerate(words, start=1)]
    for message in _pack(header, blocks):
        await callback.message.answer(message)
