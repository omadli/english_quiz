from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.middlewares.user import UserMiddleware

pytestmark = pytest.mark.asyncio


@patch("bot.middlewares.user.get_or_create_user")
async def test_middleware_injects_user_and_profile(mock_get):
    user_obj, profile_obj = MagicMock(name="user"), MagicMock(name="profile")
    mock_get.return_value = (user_obj, profile_obj, True)

    tg_user = MagicMock(id=42, username="ali", first_name="Ali", last_name=None, language_code="uz")
    handler = AsyncMock(return_value="ok")
    event = MagicMock()
    data = {"event_from_user": tg_user}

    result = await UserMiddleware()(handler, event, data)

    assert result == "ok"
    assert data["user"] is user_obj
    assert data["profile"] is profile_obj
    handler.assert_awaited_once_with(event, data)
    mock_get.assert_called_once_with(
        telegram_id=42, username="ali", first_name="Ali", last_name="", language_code="uz"
    )


@patch("bot.middlewares.user.get_or_create_user")
async def test_middleware_skips_when_no_user(mock_get):
    handler = AsyncMock(return_value="ok")
    data = {}
    result = await UserMiddleware()(handler, MagicMock(), data)
    assert result == "ok"
    assert "user" not in data
    mock_get.assert_not_called()
