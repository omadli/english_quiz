from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import group_quiz

pytestmark = pytest.mark.asyncio


async def test_is_chat_admin_true_for_administrator():
    bot = AsyncMock()
    member = MagicMock()
    member.status = "administrator"
    bot.get_chat_member.return_value = member
    assert await group_quiz.is_chat_admin(bot, -100, 5) is True


async def test_is_chat_admin_false_for_member():
    bot = AsyncMock()
    member = MagicMock()
    member.status = "member"
    bot.get_chat_member.return_value = member
    assert await group_quiz.is_chat_admin(bot, -100, 5) is False


@patch("bot.handlers.group_quiz.start_configuring", return_value=None)
@patch("bot.handlers.group_quiz.is_chat_admin", return_value=False)
async def test_cmd_quiz_rejects_non_admin(mock_admin, mock_start):
    message = AsyncMock()
    message.chat.id = -100
    message.from_user.id = 5
    message.bot = AsyncMock()
    await group_quiz.cmd_quiz(message)
    mock_start.assert_not_called()
    message.answer.assert_awaited()
