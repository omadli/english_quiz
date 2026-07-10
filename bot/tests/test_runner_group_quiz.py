from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.enums import ParseMode

from bot import runner_group_quiz

pytestmark = pytest.mark.asyncio


@patch("bot.runner_group_quiz._interval", return_value=10)
@patch("bot.runner_group_quiz._chat_id", return_value=-100)
@patch("bot.runner_group_quiz.asyncio.sleep", new_callable=AsyncMock)
@patch("bot.runner_group_quiz.finish_and_leaderboard", return_value=(-100, "🏁 board"))
@patch("bot.runner_group_quiz.is_aborted", return_value=False)
@patch("bot.runner_group_quiz.record_poll_sent")
@patch("bot.runner_group_quiz.pending_questions")
@patch("bot.runner_group_quiz.prepare_questions")
async def test_run_group_quiz_sends_polls_and_leaderboard(
    mock_prepare, mock_pending, mock_record, mock_aborted, mock_finish, mock_sleep,
    mock_chat_id, mock_interval,
):
    mock_pending.return_value = [
        {"id": 1, "prompt": "q1", "options": ["a", "b"], "correct_option": 0, "explanation": "e"},
        {"id": 2, "prompt": "q2", "options": ["a", "b"], "correct_option": 1, "explanation": "e"},
    ]
    bot = AsyncMock()
    poll_msg = MagicMock()
    poll_msg.poll.id = "poll-x"
    bot.send_poll.return_value = poll_msg

    await runner_group_quiz.run_group_quiz(bot, session_id=7)

    mock_prepare.assert_called_once_with(7)
    assert bot.send_poll.await_count == 2          # one per pending question
    assert mock_record.call_count == 2             # poll_id recorded per question
    # leaderboard sent at the end, rendered as HTML (build_leaderboard emits <b> tags)
    bot.send_message.assert_any_await(-100, "🏁 board", parse_mode=ParseMode.HTML)


@patch("bot.runner_group_quiz.asyncio.sleep", new_callable=AsyncMock)
@patch("bot.runner_group_quiz.finish_and_leaderboard", return_value=(-100, "board"))
@patch("bot.runner_group_quiz.is_aborted", return_value=True)   # aborted before it starts
@patch("bot.runner_group_quiz.record_poll_sent")
@patch("bot.runner_group_quiz.pending_questions")
@patch("bot.runner_group_quiz.prepare_questions")
async def test_run_group_quiz_stops_when_aborted(
    mock_prepare, mock_pending, mock_record, mock_aborted, mock_finish, mock_sleep
):
    """A /stop during the ready-check countdown aborts before anything runs.

    The early is_aborted() guard must short-circuit before prepare_questions,
    so no questions get built (which would clobber the ABORTED status back to
    RUNNING) and no polls/leaderboard are sent.
    """
    bot = AsyncMock()
    await runner_group_quiz.run_group_quiz(bot, session_id=7)
    mock_prepare.assert_not_called()     # aborted → never builds questions / sets RUNNING
    mock_finish.assert_not_called()      # aborted → no leaderboard for a quiz that never ran
    bot.send_poll.assert_not_awaited()   # aborted → no polls sent
