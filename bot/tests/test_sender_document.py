from unittest.mock import AsyncMock, patch

import pytest

from bot import sender

pytestmark = pytest.mark.asyncio


@patch("bot.sender._make_bot")
async def test_send_document_calls_bot(mock_make_bot):
    bot = AsyncMock()
    mock_make_bot.return_value = bot
    import asyncio

    await asyncio.to_thread(sender.send_document, 42, b"%PDF-x", "book.pdf")
    assert bot.send_document.await_count == 1
    args = bot.send_document.call_args.args
    assert args[0] == 42  # chat_id
    # the document arg is a BufferedInputFile with our filename
    assert args[1].filename == "book.pdf"
