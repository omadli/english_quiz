from unittest.mock import AsyncMock, patch

from bot import strings
from bot.handlers import menu


async def test_cmd_menu_clears_and_shows_keyboard():
    message = AsyncMock()
    state = AsyncMock()
    await menu.cmd_menu(message, state)
    state.clear.assert_awaited()
    message.answer.assert_awaited()
    assert message.answer.call_args.kwargs.get("reply_markup") is not None


async def test_menu_group_quiz_sends_info():
    message = AsyncMock()
    await menu.menu_group_quiz(message)
    message.answer.assert_awaited()
    assert strings.GROUP_QUIZ_INFO in message.answer.call_args.args


@patch("bot.handlers.menu.cmd_book", new_callable=AsyncMock)
async def test_menu_books_delegates(mock_cmd_book):
    message = AsyncMock()
    await menu.menu_books(message)
    mock_cmd_book.assert_awaited_once_with(message)


@patch("bot.handlers.menu.cmd_top", new_callable=AsyncMock)
async def test_menu_top_delegates(mock_cmd_top):
    message = AsyncMock()
    user = object()
    await menu.menu_top(message, user)
    mock_cmd_top.assert_awaited_once_with(message, user)


@patch("bot.handlers.menu.cmd_settings", new_callable=AsyncMock)
async def test_menu_settings_delegates(mock_cmd_settings):
    message = AsyncMock()
    state = AsyncMock()
    profile = object()
    await menu.menu_settings(message, state, profile)
    mock_cmd_settings.assert_awaited_once_with(message, state, profile)
