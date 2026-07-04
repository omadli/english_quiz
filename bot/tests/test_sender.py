from unittest.mock import AsyncMock

import pytest

from bot import sender

pytestmark = pytest.mark.asyncio


async def test_send_daily_sends_card_then_items():
    bot = AsyncMock()
    items = [
        {"caption": "afraid — qo'rqib", "image": b"IMG", "audio": b"AUD"},
        {"caption": "agree — rozi", "image": None, "audio": None},
    ]
    await sender._send_daily(bot, 555, b"CARD", items)

    # 1 card photo + 1 word photo (item 1) = 2 send_photo; item 2 has no image → send_message
    assert bot.send_photo.await_count == 2
    assert bot.send_message.await_count == 1
    assert bot.send_audio.await_count == 1  # only item 1 has audio


async def test_send_daily_no_card():
    bot = AsyncMock()
    await sender._send_daily(bot, 555, None, [{"caption": "x", "image": None, "audio": None}])
    assert bot.send_photo.await_count == 0
    assert bot.send_message.await_count == 1
