from unittest.mock import MagicMock, patch

import pytest

from bot.handlers import quiz

pytestmark = pytest.mark.asyncio


def _poll_answer():
    pa = MagicMock()
    pa.poll_id = "poll-1"
    pa.option_ids = [2]
    pa.user.id = 555
    pa.user.username = "ali"
    pa.user.full_name = "Ali"
    return pa


@patch("bot.handlers.quiz.record_answer")
@patch("bot.handlers.quiz.record_group_answer", return_value=True)
async def test_group_answer_handled_skips_personal(mock_group, mock_personal):
    await quiz.on_poll_answer(_poll_answer())
    mock_group.assert_called_once_with("poll-1", [2], 555, "ali", "Ali")
    mock_personal.assert_not_called()


@patch("bot.handlers.quiz.record_answer")
@patch("bot.handlers.quiz.record_group_answer", return_value=False)
async def test_non_group_falls_back_to_personal(mock_group, mock_personal):
    await quiz.on_poll_answer(_poll_answer())
    mock_group.assert_called_once()
    mock_personal.assert_called_once_with("poll-1", [2])
