from unittest.mock import AsyncMock

import pytest

from bot import sender

pytestmark = pytest.mark.asyncio


async def test_send_daily_audio_with_caption_and_button():
    bot = AsyncMock()
    await sender._send_daily(bot, 555, "caption list", b"AUD", "https://x/webapp/?view=today")
    bot.send_audio.assert_awaited_once()
    kwargs = bot.send_audio.await_args.kwargs
    assert kwargs["caption"] == "caption list"
    assert kwargs["reply_markup"] is not None  # 📖 Batafsil button
    bot.send_message.assert_not_awaited()


async def test_send_daily_no_audio_sends_message():
    bot = AsyncMock()
    await sender._send_daily(bot, 555, "caption", None, None)
    bot.send_message.assert_awaited_once()
    bot.send_audio.assert_not_awaited()


async def test_send_daily_long_caption_splits_message_and_audio():
    bot = AsyncMock()
    await sender._send_daily(bot, 555, "x" * 1100, b"AUD", None)
    bot.send_message.assert_awaited_once()  # list as its own message
    bot.send_audio.assert_awaited_once()    # audio with a short caption


async def test_send_daily_no_button_when_no_url():
    bot = AsyncMock()
    await sender._send_daily(bot, 555, "caption", b"AUD", None)
    assert bot.send_audio.await_args.kwargs["reply_markup"] is None
