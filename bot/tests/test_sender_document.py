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


@patch("bot.sender._make_bot")
async def test_send_document_by_file_id_passes_id_through(mock_make_bot):
    import asyncio

    bot = AsyncMock()
    bot.send_document.return_value.document.file_id = "RETURNED"
    mock_make_bot.return_value = bot
    fid = await asyncio.to_thread(sender.send_document, 42, "CACHED_ID", "x.pdf")
    assert bot.send_document.call_args.args[1] == "CACHED_ID"  # sent as-is, no upload
    assert fid == "RETURNED"
