import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, PollType
from aiogram.types import BufferedInputFile

from bot.config import get_bot_token


def _make_bot() -> Bot:
    return Bot(token=get_bot_token(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def _send_daily(bot: Bot, chat_id: int, card: bytes | None, items: list[dict]) -> None:
    if card:
        await bot.send_photo(chat_id, BufferedInputFile(card, "card.png"))
    for item in items:
        if item.get("image"):
            await bot.send_photo(
                chat_id, BufferedInputFile(item["image"], "word.jpg"), caption=item["caption"]
            )
        else:
            await bot.send_message(chat_id, item["caption"])
        if item.get("audio"):
            await bot.send_audio(chat_id, BufferedInputFile(item["audio"], "word.mp3"))


def send_daily(chat_id: int, card: bytes | None, items: list[dict]) -> None:
    async def _run() -> None:
        bot = _make_bot()
        try:
            await _send_daily(bot, chat_id, card, items)
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
) -> str:
    msg = await bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=options,
        type=PollType.QUIZ,
        correct_option_id=correct_option,
        is_anonymous=False,
        explanation=explanation,
    )
    return msg.poll.id


def send_quiz_poll(
    chat_id: int,
    question: str,
    options: list[str],
    correct_option: int,
    explanation: str | None = None,
) -> str:
    async def _run() -> str:
        bot = _make_bot()
        try:
            return await _send_quiz_poll(
                bot, chat_id, question, options, correct_option, explanation
            )
        finally:
            await bot.session.close()

    return asyncio.run(_run())
