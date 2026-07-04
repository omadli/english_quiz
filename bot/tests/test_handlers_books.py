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


@patch("bot.handlers.books.send_document")
@patch("bot.handlers.books.get_book_document")
async def test_send_pdf_sends_document(mock_get, mock_send):
    mock_get.return_value = ("book-1-lugat.pdf", b"%PDF-x")
    callback = AsyncMock()
    callback.data = "pdf:book:1"
    callback.message.chat.id = 55
    await books.send_pdf(callback)
    mock_send.assert_called_once()
    assert mock_send.call_args.args[0] == 55
    assert mock_send.call_args.args[2] == "book-1-lugat.pdf"


@patch("bot.handlers.books.send_document")
@patch("bot.handlers.books.get_book_document", return_value=None)
async def test_send_pdf_missing_book(mock_get, mock_send):
    callback = AsyncMock()
    callback.data = "pdf:book:999"
    await books.send_pdf(callback)
    mock_send.assert_not_called()
