from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import books

pytestmark = pytest.mark.asyncio


@patch("bot.handlers.books.active_books")
async def test_cmd_book_lists_books(mock_books):
    b = MagicMock()
    b.pk = 1
    b.title = "Book 1"
    mock_books.return_value = [b]
    message = AsyncMock()
    await books.cmd_book(message)
    message.answer.assert_awaited()


@patch("bot.handlers.books.active_books", return_value=[])
async def test_cmd_book_no_books(mock_books):
    message = AsyncMock()
    await books.cmd_book(message)
    message.answer.assert_awaited()


@patch("bot.handlers.books.save_file_id")
@patch("bot.handlers.books.send_document", return_value="NEWID")
@patch("bot.handlers.books.get_sendable_book")
async def test_send_pdf_uploads_then_caches_file_id(mock_get, mock_send, mock_save):
    mock_get.return_value = ("Book 1.pdf", b"%PDF-x")  # bytes → upload
    callback = AsyncMock()
    callback.data = "pdf:book:1"
    callback.message.chat.id = 55
    await books.send_pdf(callback)
    assert mock_send.call_args.args[1] == b"%PDF-x"
    mock_save.assert_called_once_with(1, "NEWID")


@patch("bot.handlers.books.save_file_id")
@patch("bot.handlers.books.send_document", return_value="CACHED")
@patch("bot.handlers.books.get_sendable_book")
async def test_send_pdf_uses_cached_file_id_without_resaving(mock_get, mock_send, mock_save):
    mock_get.return_value = ("Book 1.pdf", "CACHED")  # str → cached file_id
    callback = AsyncMock()
    callback.data = "pdf:book:1"
    callback.message.chat.id = 55
    await books.send_pdf(callback)
    assert mock_send.call_args.args[1] == "CACHED"
    mock_save.assert_not_called()


@patch("bot.handlers.books.send_document")
@patch("bot.handlers.books.get_sendable_book", return_value=None)
async def test_send_pdf_missing_book(mock_get, mock_send):
    callback = AsyncMock()
    callback.data = "pdf:book:999"
    await books.send_pdf(callback)
    mock_send.assert_not_called()
