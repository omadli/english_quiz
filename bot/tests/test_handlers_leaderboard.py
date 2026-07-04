from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import leaderboard


def _entry(rank, name, points, sessions):
    return {"rank": rank, "user_id": rank, "name": name, "points": points, "sessions": sessions}


def test_format_leaderboard_lists_entries():
    text = leaderboard._format_leaderboard(
        [_entry(1, "Alice", 10, 3), _entry(2, "Bob", 8, 2)], None
    )
    assert "Alice" in text
    assert "Bob" in text
    assert "🥇" in text


def test_format_leaderboard_appends_own_rank_when_outside_top():
    text = leaderboard._format_leaderboard([_entry(1, "Alice", 10, 3)], (15, 4))
    assert "15" in text  # own rank shown because 15 > len(entries)=1


def test_format_leaderboard_empty():
    assert leaderboard._format_leaderboard([], None) == leaderboard.strings.TOP_EMPTY


@patch("bot.handlers.leaderboard.user_month_rank", return_value=None)
@patch("bot.handlers.leaderboard.build_monthly_leaderboard")
async def test_cmd_top_sends_board(mock_board, mock_rank):
    mock_board.return_value = [_entry(1, "Alice", 10, 3)]
    message = AsyncMock()
    await leaderboard.cmd_top(message, user=MagicMock())
    message.answer.assert_awaited()
    sent = message.answer.call_args.args[0]
    assert "Alice" in sent
