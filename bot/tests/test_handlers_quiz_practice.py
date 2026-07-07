import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from bot import strings
from bot.handlers import quiz_practice as qp


@patch("bot.handlers.quiz_practice._active_books")
async def test_menu_test_lists_books(mock_books):
    mock_books.return_value = [MagicMock(pk=1, title="Book 1")]
    message, state = AsyncMock(), AsyncMock()
    await qp.menu_test(message, state)
    state.clear.assert_awaited()
    message.answer.assert_awaited()


@patch("bot.handlers.quiz_practice._book_units")
async def test_pq_book_sets_units_state(mock_units):
    mock_units.return_value = [MagicMock(pk=10, number=1)]
    cb, state = AsyncMock(), AsyncMock()
    cb.data = "pq:book:1"
    await qp.pq_book(cb, state)
    state.set_state.assert_awaited()
    cb.message.edit_text.assert_awaited()


@patch("bot.handlers.quiz_practice._book_units", return_value=[])
async def test_pq_toggle_unit_adds_selection(mock_units):
    cb, state = AsyncMock(), AsyncMock()
    cb.data = "pq:u:10"
    state.get_data.return_value = {"book_id": 1, "sel": []}
    await qp.pq_toggle_unit(cb, state)
    state.update_data.assert_awaited_with(sel=[10])


async def test_pq_next_requires_a_selection():
    cb, state = AsyncMock(), AsyncMock()
    state.get_data.return_value = {"sel": []}
    await qp.pq_next(cb, state)
    cb.answer.assert_awaited()  # alert
    cb.message.edit_text.assert_not_awaited()


async def test_pq_next_advances_to_count():
    cb, state = AsyncMock(), AsyncMock()
    state.get_data.return_value = {"sel": [10]}
    await qp.pq_next(cb, state)
    state.set_state.assert_awaited()
    cb.message.edit_text.assert_awaited()


async def test_pq_count_advances_to_time():
    cb, state = AsyncMock(), AsyncMock()
    cb.data = "pq:count:20"
    await qp.pq_count(cb, state)
    state.update_data.assert_awaited_with(count=20)
    cb.message.edit_text.assert_awaited()


@patch("bot.handlers.quiz_practice._summary_data", return_value=("Book 1", [1, 2]))
async def test_pq_types_done_shows_summary(mock_sum):
    cb, state = AsyncMock(), AsyncMock()
    state.get_data.return_value = {"book_id": 1, "sel": [10, 11], "count": 20, "interval": 30}
    await qp.pq_types_done(cb, state)
    cb.message.edit_text.assert_awaited()
    text = cb.message.edit_text.call_args.args[0]
    assert "Book 1" in text and "20" in text


@patch("bot.handlers.quiz_practice.asyncio.create_task")
@patch("bot.handlers.quiz_practice._countdown_then_run", new_callable=MagicMock)
@patch("bot.handlers.quiz_practice._build_quiz")
async def test_pq_start_builds_and_launches(mock_build, mock_run, mock_task):
    mock_build.return_value = [
        {"prompt": "a", "options": ["a", "b"], "correct_option": 0, "explanation": "x"}
    ]
    cb, state = AsyncMock(), AsyncMock()
    state.get_data.return_value = {"sel": [10], "count": 10, "interval": 30, "types": ["en_uz"]}
    await qp.pq_start(cb, state)
    state.clear.assert_awaited()
    mock_task.assert_called_once()


async def test_register_answer_wakes_runner_and_records_choice():
    event = asyncio.Event()
    qp._pending["p1"] = {"event": event, "chosen": None}
    assert qp.register_answer("p1", [2]) is True
    assert event.is_set()
    assert qp._pending["p1"]["chosen"] == 2
    qp._pending.clear()


def test_register_answer_ignores_unknown_poll():
    assert qp.register_answer("unknown", [0]) is False


def _raise_timeout(coro, *args, **kwargs):
    coro.close()
    raise TimeoutError


@patch("bot.handlers.quiz_practice.asyncio.wait_for", side_effect=_raise_timeout)
async def test_run_quiz_pauses_after_two_consecutive_skips(mock_wait):
    bot = AsyncMock()
    bot.send_poll.return_value.poll.id = "p"
    questions = [
        {"prompt": str(i), "options": ["a", "b"], "correct_option": 0, "explanation": "x"}
        for i in range(5)
    ]
    await qp.run_personal_quiz(bot, 55, questions, timer=30)
    assert bot.send_poll.await_count == 2
    sent = [c.args[1] for c in bot.send_message.await_args_list]
    assert strings.QUIZ_PAUSED in sent
