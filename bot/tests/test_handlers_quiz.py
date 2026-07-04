from unittest.mock import MagicMock, patch

import pytest

from bot.handlers import quiz

pytestmark = pytest.mark.asyncio


@patch("bot.handlers.quiz.record_answer")
async def test_poll_answer_handler_calls_record(mock_record):
    poll_answer = MagicMock()
    poll_answer.poll_id = "poll-1"
    poll_answer.option_ids = [2]
    await quiz.on_poll_answer(poll_answer)
    mock_record.assert_called_once_with("poll-1", [2])
