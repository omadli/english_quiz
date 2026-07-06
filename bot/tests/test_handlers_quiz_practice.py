from unittest.mock import AsyncMock, MagicMock, patch

from bot import strings
from bot.handlers import quiz_practice as qp


@patch("bot.handlers.quiz_practice._active_books")
async def test_menu_test_lists_books(mock_books):
    mock_books.return_value = [MagicMock(pk=1, title="Book 1")]
    message = AsyncMock()
    await qp.menu_test(message)
    message.answer.assert_awaited()
    assert message.answer.call_args.kwargs.get("reply_markup") is not None


@patch("bot.handlers.quiz_practice._active_books", return_value=[])
async def test_menu_test_no_books(mock_books):
    message = AsyncMock()
    await qp.menu_test(message)
    assert strings.NO_BOOKS in message.answer.call_args.args


@patch("bot.handlers.quiz_practice._build_quiz")
async def test_pq_unit_sends_quiz_polls_then_done(mock_build):
    mock_build.return_value = [
        {"prompt": "afraid", "options": ["a", "b", "c", "d"],
         "correct_option": 0, "explanation": "@x"},
        {"prompt": "agree", "options": ["a", "b", "c", "d"],
         "correct_option": 1, "explanation": "@x"},
    ]
    callback = AsyncMock()
    callback.data = "pq:unit:3"
    callback.message.chat.id = 77
    bot = AsyncMock()
    callback.message.bot = bot
    await qp.pq_unit(callback)
    assert bot.send_poll.await_count == 2
    # every poll is a native quiz with a correct option
    for call in bot.send_poll.await_args_list:
        assert call.kwargs["type"] == "quiz"
        assert "correct_option_id" in call.kwargs
    bot.send_message.assert_awaited()


@patch("bot.handlers.quiz_practice._build_quiz", return_value=[])
async def test_pq_unit_no_words(mock_build):
    callback = AsyncMock()
    callback.data = "pq:unit:3"
    await qp.pq_unit(callback)
    callback.message.edit_text.assert_awaited()
    assert strings.QUIZ_NO_WORDS in callback.message.edit_text.call_args.args
