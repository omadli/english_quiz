from unittest.mock import AsyncMock, MagicMock, patch

from bot import strings
from bot.handlers import words


def test_format_words_lists_en_uz_pos():
    unit = MagicMock()
    unit.book.title = "Book 1"
    unit.number = 3
    w = MagicMock(en="afraid", uz="qo'rqqan, cho'chigan", part_of_speech="adj.")
    text = words.format_words(unit, [w])
    assert "afraid" in text
    assert "qo'rqqan, cho'chigan" in text
    assert "adj." in text
    assert "Book 1" in text
    assert "Unit 3" in text


@patch("bot.handlers.words._active_books")
async def test_menu_words_lists_books(mock_books):
    b = MagicMock(pk=1, title="Book 1")
    mock_books.return_value = [b]
    message = AsyncMock()
    await words.menu_words(message)
    message.answer.assert_awaited()
    assert message.answer.call_args.kwargs.get("reply_markup") is not None


@patch("bot.handlers.words._active_books", return_value=[])
async def test_menu_words_no_books(mock_books):
    message = AsyncMock()
    await words.menu_words(message)
    assert strings.NO_BOOKS in message.answer.call_args.args


@patch("bot.handlers.words._unit_with_words")
async def test_wl_unit_shows_word_list(mock_uw):
    unit = MagicMock(number=1, book_id=1)
    unit.book.title = "Book 1"
    w = MagicMock(en="afraid", uz="qo'rqqan", part_of_speech="adj.")
    mock_uw.return_value = (unit, [w])
    callback = AsyncMock()
    callback.data = "wl:unit:5"
    await words.wl_unit(callback)
    callback.message.edit_text.assert_awaited()
    assert "afraid" in callback.message.edit_text.call_args.args[0]


@patch("bot.handlers.words._unit_with_words", return_value=None)
async def test_wl_unit_missing_unit_noops(mock_uw):
    callback = AsyncMock()
    callback.data = "wl:unit:999"
    await words.wl_unit(callback)
    callback.message.edit_text.assert_not_awaited()
