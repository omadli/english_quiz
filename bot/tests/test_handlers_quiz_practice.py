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


@patch("bot.handlers.quiz_practice._summary_and_code",
       return_value=("Book 1", [1, 2], "b1u1-2c20t30qEUD"))
async def test_pq_types_done_shows_summary_with_code(mock_sum):
    cb, state = AsyncMock(), AsyncMock()
    state.get_data.return_value = {"book_id": 1, "sel": [10, 11], "count": 20, "interval": 30}
    await qp.pq_types_done(cb, state)
    cb.message.edit_text.assert_awaited()
    text = cb.message.edit_text.call_args.args[0]
    assert "Book 1" in text and "20" in text
    # the share button carries the self-contained code (switch_inline_query)
    kb = cb.message.edit_text.call_args.kwargs["reply_markup"]
    codes = [b.switch_inline_query for row in kb.inline_keyboard for b in row
             if b.switch_inline_query]
    assert "b1u1-2c20t30qEUD" in codes


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


@patch("bot.handlers.quiz_practice.dj_settings")
@patch("bot.handlers.quiz_practice.card_for")
async def test_inline_share_returns_card_with_action_buttons(mock_card, mock_settings):
    """Inline query = the share code → a card whose buttons start personal/group + re-share."""
    mock_settings.BOT_USERNAME = "learn_bot"
    mock_card.return_value = {
        "book": "Book 1", "units": "1–4", "count": 10, "interval": 30, "types": ["en_uz"]
    }
    query = AsyncMock()
    query.query = "b1u1-4c10t30qE"
    await qp.inline_share(query)
    results = query.answer.await_args.args[0]
    assert results[0].id == "b1u1-4c10t30qE"
    assert "Book 1" in results[0].title              # book shown in the inline preview
    assert "1–4" in results[0].description           # units shown in the inline preview
    buttons = [b for row in results[0].reply_markup.inline_keyboard for b in row]
    urls = [b.url for b in buttons if b.url]
    assert any("start=b1u1-4c10t30qE" in u for u in urls)        # personal deep link
    assert any("startgroup=b1u1-4c10t30qE" in u for u in urls)   # group deep link
    assert any(b.switch_inline_query == "b1u1-4c10t30qE" for b in buttons)  # re-share


@patch("bot.handlers.quiz_practice.dj_settings")
@patch("bot.handlers.quiz_practice.card_for", return_value=None)
async def test_inline_share_invalid_code_shows_hint(mock_card, mock_settings):
    mock_settings.BOT_USERNAME = "learn_bot"
    query = AsyncMock()
    query.query = "garbage"
    await qp.inline_share(query)
    results = query.answer.await_args.args[0]
    assert results[0].id == "none"


@patch("bot.handlers.quiz_practice._countdown_then_run", new_callable=AsyncMock)
@patch("bot.handlers.quiz_practice._build_quiz")
async def test_start_shared_quiz_sends_ready_and_runs(mock_build, mock_countdown):
    mock_build.return_value = [
        {"prompt": "a", "options": ["a", "b"], "correct_option": 0, "explanation": "x"}
    ]
    bot = AsyncMock()
    bot.send_message.return_value.message_id = 99
    await qp.start_shared_quiz(bot, 777, [10], 10, 30, ["en_uz"])
    bot.send_message.assert_awaited()  # ready prompt
    mock_countdown.assert_awaited_once()


@patch("bot.handlers.quiz_practice._build_quiz", return_value=[])
async def test_start_shared_quiz_no_words_bails(mock_build):
    bot = AsyncMock()
    await qp.start_shared_quiz(bot, 777, [10], 10, 30, None)
    assert strings.QUIZ_NO_WORDS in bot.send_message.call_args.args


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
