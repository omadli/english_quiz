import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import settings as settings_handler

pytestmark = pytest.mark.asyncio


@patch("bot.handlers.settings.sync_to_async")
async def test_toggle_nudges_flips_and_rerenders(mock_sta):
    # sync_to_async(fn) -> returns an async callable that just runs fn
    def _wrap(fn):
        async def _inner(*a, **k):
            return fn(*a, **k)
        return _inner
    mock_sta.side_effect = _wrap

    profile = MagicMock()
    profile.nudges_enabled = True
    profile.study_weekdays = [0, 1, 2]
    profile.audio_enabled = True
    # format_profile (invoked by toggle_nudges to re-render) also reads these;
    # give it real values so the strftime format specs don't hit MagicMock.__format__.
    profile.words_per_session = 10
    profile.morning_time = datetime.time(7, 0)
    profile.exam_time = datetime.time(20, 0)
    callback = AsyncMock()
    await settings_handler.toggle_nudges(callback, profile=profile)
    assert profile.nudges_enabled is False  # flipped
    callback.message.edit_text.assert_awaited()
