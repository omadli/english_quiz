import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, PollType
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from bot.config import get_bot_token


def _make_bot() -> Bot:
    return Bot(token=get_bot_token(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def _batafsil_markup(webapp_url: str | None) -> InlineKeyboardMarkup | None:
    if not webapp_url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📖 Batafsil", web_app=WebAppInfo(url=webapp_url))
    ]])


async def _send_daily(
    bot: Bot, chat_id: int, caption: str, audio: bytes | None, webapp_url: str | None = None
) -> None:
    """Morning task: one audio (caption = the word list) + a 'Batafsil' WebApp button.
    If there's no audio, send the list as a plain message; if the caption exceeds
    Telegram's 1024-char media caption cap, send the list first, then a short audio."""
    markup = _batafsil_markup(webapp_url)
    if audio is None:
        await bot.send_message(chat_id, caption, reply_markup=markup)
        return
    if len(caption) > 1024:
        await bot.send_message(chat_id, caption)
        await bot.send_audio(
            chat_id, BufferedInputFile(audio, "words.mp3"),
            caption="🔊 Bugungi so'zlar", reply_markup=markup,
        )
    else:
        await bot.send_audio(
            chat_id, BufferedInputFile(audio, "words.mp3"),
            caption=caption, reply_markup=markup,
        )


def send_daily(
    chat_id: int, caption: str, audio: bytes | None, webapp_url: str | None = None
) -> None:
    async def _run() -> None:
        bot = _make_bot()
        try:
            await _send_daily(bot, chat_id, caption, audio, webapp_url)
        finally:
            await bot.session.close()

    asyncio.run(_run())


def send_text(chat_id: int, text: str) -> None:
    """Send a plain HTML text message (reports, nudges, referrals)."""

    async def _run() -> None:
        bot = _make_bot()
        try:
            await bot.send_message(chat_id, text)
        finally:
            await bot.session.close()

    asyncio.run(_run())


def send_exam_prompt(chat_id: int, text: str, webapp_url: str | None = None) -> None:
    """Exam reminder/start-gate: a message + a '▶️ Imtihonni boshlash' WebApp button
    (opens the sectioned Mini App exam) instead of dumping quiz polls."""
    markup = None
    if webapp_url:
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="▶️ Imtihonni boshlash", web_app=WebAppInfo(url=webapp_url))
        ]])

    async def _run() -> None:
        bot = _make_bot()
        try:
            await bot.send_message(chat_id, text, reply_markup=markup)
        finally:
            await bot.session.close()

    asyncio.run(_run())


async def _send_quiz_poll(
    bot: Bot,
    chat_id: int,
    question: str,
    options: list[str],
    correct_option: int,
    explanation: str | None = None,
    is_anonymous: bool = False,
) -> str:
    msg = await bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=options,
        type=PollType.QUIZ,
        correct_option_id=correct_option,
        is_anonymous=is_anonymous,
        explanation=explanation,
        explanation_parse_mode=ParseMode.HTML,
    )
    return msg.poll.id


def send_quiz_poll(
    chat_id: int,
    question: str,
    options: list[str],
    correct_option: int,
    explanation: str | None = None,
    is_anonymous: bool = False,
) -> str:
    async def _run() -> str:
        bot = _make_bot()
        try:
            return await _send_quiz_poll(
                bot, chat_id, question, options, correct_option, explanation, is_anonymous
            )
        finally:
            await bot.session.close()

    return asyncio.run(_run())


async def _send_document(bot: Bot, chat_id: int, document: bytes | str, filename: str) -> str:
    # `document` is either raw bytes (upload) or a Telegram file_id (str, no re-upload).
    input_doc = document if isinstance(document, str) else BufferedInputFile(document, filename)
    msg = await bot.send_document(chat_id, input_doc)
    return msg.document.file_id


def send_document(chat_id: int, document: bytes | str, filename: str = "") -> str:
    """Send a document (bytes to upload, or a cached file_id) and return its file_id."""

    async def _run() -> str:
        bot = _make_bot()
        try:
            return await _send_document(bot, chat_id, document, filename)
        finally:
            await bot.session.close()

    return asyncio.run(_run())
