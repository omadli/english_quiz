from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot import sender

pytestmark = pytest.mark.asyncio


@patch("bot.sender._make_bot")
async def test_send_quiz_poll_anonymous_flag(mock_make_bot):
    bot = AsyncMock()
    msg = MagicMock()
    msg.poll.id = "PID"
    bot.send_poll.return_value = msg
    mock_make_bot.return_value = bot
    # sync wrapper; call in a thread to avoid nested-loop issues
    import asyncio
    poll_id = await asyncio.to_thread(
        sender.send_quiz_poll, 42, "Q", ["a", "b"], 0, "expl", True
    )
    assert poll_id == "PID"
    assert bot.send_poll.call_args.kwargs["is_anonymous"] is True
