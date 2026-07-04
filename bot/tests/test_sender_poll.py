from unittest.mock import AsyncMock, MagicMock

import pytest

from bot import sender

pytestmark = pytest.mark.asyncio


async def test_send_quiz_poll_returns_poll_id_and_sets_quiz_type():
    bot = AsyncMock()
    msg = MagicMock()
    msg.poll.id = "poll-xyz"
    bot.send_poll.return_value = msg

    poll_id = await sender._send_quiz_poll(
        bot, 555, "Question?", ["a", "b", "c", "d"], 2, explanation="expl"
    )
    assert poll_id == "poll-xyz"
    kwargs = bot.send_poll.call_args.kwargs
    assert kwargs["correct_option_id"] == 2
    assert kwargs["is_anonymous"] is False
