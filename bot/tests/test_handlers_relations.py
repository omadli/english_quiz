from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import relations

pytestmark = pytest.mark.asyncio


async def test_bot_username_from_settings(settings):
    settings.BOT_USERNAME = "mybot"
    assert await relations.bot_username(AsyncMock()) == "mybot"


async def test_bot_username_falls_back_to_get_me(settings):
    settings.BOT_USERNAME = ""
    bot = AsyncMock()
    me = MagicMock()
    me.username = "runtimebot"
    bot.get_me.return_value = me
    assert await relations.bot_username(bot) == "runtimebot"


@patch("bot.handlers.relations.create_referral_token")
async def test_cmd_parent_sends_deep_link(mock_create, settings):
    settings.BOT_USERNAME = "mybot"
    token = MagicMock()
    token.token = "TOK123"
    mock_create.return_value = token
    message = AsyncMock()
    message.bot = AsyncMock()
    await relations.cmd_parent(message, user=MagicMock())
    mock_create.assert_called_once()
    sent = message.answer.call_args.args[0]
    assert "t.me/mybot?start=gTOK123" in sent
