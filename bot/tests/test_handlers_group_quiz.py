from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import sync_to_async
from django.db import connections

from apps.catalog.models import Book, Unit
from apps.quiz.services.session import get_active_session, set_book, start_configuring
from bot.handlers import group_quiz

pytestmark = pytest.mark.asyncio


async def test_is_chat_admin_true_for_administrator():
    bot = AsyncMock()
    member = MagicMock()
    member.status = "administrator"
    bot.get_chat_member.return_value = member
    assert await group_quiz.is_chat_admin(bot, -100, 5) is True


async def test_is_chat_admin_false_for_member():
    bot = AsyncMock()
    member = MagicMock()
    member.status = "member"
    bot.get_chat_member.return_value = member
    assert await group_quiz.is_chat_admin(bot, -100, 5) is False


@patch("bot.handlers.group_quiz.start_configuring", return_value=None)
@patch("bot.handlers.group_quiz.is_chat_admin", return_value=False)
async def test_cmd_quiz_rejects_non_admin(mock_admin, mock_start):
    message = AsyncMock()
    message.chat.id = -100
    message.from_user.id = 5
    message.bot = AsyncMock()
    await group_quiz.cmd_quiz(message)
    mock_start.assert_not_called()
    message.answer.assert_awaited()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_toggle_unit_cb_no_sync_only_error():
    """Regression test for a `SynchronousOnlyOperation` bug in `toggle_unit_cb`.

    `toggle_unit_cb` used to read `session.book` (a lazy FK) directly inside
    an `async def`, which raises `SynchronousOnlyOperation` under a real
    event loop. It's now read via the `sync_to_async`-wrapped `_book_number`
    helper. This test drives the handler against a real DB session (no
    mocked services) so an unwrapped ORM access would actually trip Django's
    async-safety guard, unlike the other tests in this module which mock the
    services and therefore never touch the ORM at all.
    """
    chat_id = -100777

    def _setup() -> tuple[Book, Unit]:
        book = Book.objects.create(number=1, title="B1", slug="b1-toggle-cb")
        unit1 = Unit.objects.create(book=book, number=1)
        Unit.objects.create(book=book, number=2)
        session = start_configuring(chat_id, 999555)
        set_book(session, book.number)
        return unit1

    try:
        unit1 = await sync_to_async(_setup)()

        callback = AsyncMock()
        callback.message.chat.id = chat_id
        callback.from_user.id = 999555
        callback.data = f"gq:unit:{unit1.id}"
        callback.message.edit_reply_markup = AsyncMock()
        callback.answer = AsyncMock()

        await group_quiz.toggle_unit_cb(callback)

        session = await sync_to_async(get_active_session)(chat_id)
        assert unit1.id in session.unit_ids
        callback.message.edit_reply_markup.assert_awaited()
    finally:
        # `sync_to_async` (thread-sensitive) runs all of the ORM calls above
        # on one worker thread, which opens its own DB connection that
        # Django never closes automatically (no request/response cycle to
        # hook into, unlike a real ASGI request). Close it explicitly, on
        # that same thread, so it doesn't linger and make the test database
        # teardown fail with "database is being accessed by other users".
        await sync_to_async(connections.close_all)()


@patch("bot.handlers.group_quiz.get_active_session")
async def test_start_quiz_rejects_non_owner(mock_get_session):
    """A group member who did not start the wizard can't open the ready-check.

    `session.started_by_telegram_id` (111) differs from the tapping user
    (999), so `_owned_session` must reject the callback with an alert and
    `start_quiz` must never edit the message into the ready-check.
    """
    session = MagicMock()
    session.started_by_telegram_id = 111
    session.id = 43
    mock_get_session.return_value = session
    group_quiz._ready.pop(43, None)

    callback = AsyncMock()
    callback.from_user.id = 999
    callback.message.chat.id = -100
    callback.answer = AsyncMock()

    await group_quiz.start_quiz(callback)

    callback.message.edit_text.assert_not_awaited()
    assert 43 not in group_quiz._ready
    callback.answer.assert_awaited_with(group_quiz._NOT_OWNER, show_alert=True)


@patch("bot.handlers.group_quiz.get_active_session")
async def test_start_quiz_owner_opens_ready_check(mock_get_session):
    """The admin who started the wizard opens the ready-check (no launch yet)."""
    session = MagicMock()
    session.started_by_telegram_id = 111
    session.id = 42
    mock_get_session.return_value = session

    callback = AsyncMock()
    callback.from_user.id = 111
    callback.message.chat.id = -100
    callback.answer = AsyncMock()

    try:
        await group_quiz.start_quiz(callback)
        assert group_quiz._ready[42] == {}
        callback.message.edit_text.assert_awaited_once()
    finally:
        group_quiz._ready.pop(42, None)


@patch("bot.handlers.group_quiz.get_active_session")
async def test_toggle_ready_adds_then_removes(mock_get_session):
    """Tapping «Men tayyorman» adds the user, tapping again removes them."""
    session = MagicMock()
    session.id = 7
    mock_get_session.return_value = session
    group_quiz._ready.pop(7, None)

    callback = AsyncMock()
    callback.from_user.id = 5
    callback.from_user.full_name = "Ali"
    callback.message.chat.id = -100
    callback.answer = AsyncMock()

    try:
        await group_quiz.toggle_ready(callback)
        assert group_quiz._ready[7] == {5: "Ali"}
        await group_quiz.toggle_ready(callback)
        assert group_quiz._ready[7] == {}
    finally:
        group_quiz._ready.pop(7, None)


@patch("bot.handlers.group_quiz.asyncio.create_task")
@patch("bot.handlers.group_quiz.get_active_session")
async def test_go_quiz_blocks_when_no_one_ready(mock_get_session, mock_create_task):
    """Owner can't launch with an empty ready set — gets an alert, nothing runs."""
    session = MagicMock()
    session.started_by_telegram_id = 111
    session.id = 8
    mock_get_session.return_value = session
    group_quiz._ready[8] = {}

    callback = AsyncMock()
    callback.from_user.id = 111
    callback.message.chat.id = -100
    callback.answer = AsyncMock()

    try:
        await group_quiz.go_quiz(callback)
        mock_create_task.assert_not_called()
        callback.answer.assert_awaited_with(group_quiz._NO_ONE_READY, show_alert=True)
    finally:
        group_quiz._ready.pop(8, None)


@patch("bot.handlers.group_quiz.create_group_session_from_config")
async def test_seed_group_quiz_opens_ready_check(mock_create):
    """`?startgroup=<code>` seeds a session from a config and posts the ready-check."""
    mock_create.return_value = MagicMock(id=12)
    group_quiz._ready.pop(12, None)
    bot = AsyncMock()
    cfg = {"book_id": 1, "unit_ids": [1, 2], "count": 10, "interval": 30, "types": ["en_uz"]}
    try:
        await group_quiz.seed_group_quiz_from_config(bot, -100, 555, cfg)
        assert group_quiz._ready[12] == {}
        bot.send_message.assert_awaited_once()
        assert bot.send_message.call_args.kwargs.get("reply_markup") is not None
    finally:
        group_quiz._ready.pop(12, None)


@patch("bot.handlers.group_quiz.create_group_session_from_config", return_value=None)
async def test_seed_group_quiz_blocks_when_active(mock_create):
    """If a quiz is already running in the chat, the seed just says so."""
    bot = AsyncMock()
    await group_quiz.seed_group_quiz_from_config(bot, -100, 555, {})
    assert group_quiz._ALREADY in bot.send_message.call_args.args


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_config_text_summarizes_book_units_count_time():
    """The ready-check config line shows book, unit numbers, count and interval."""
    from apps.quiz.models import GroupQuizSession

    def _setup() -> GroupQuizSession:
        book = Book.objects.create(number=1, title="B1", slug="b1-cfg")
        u1 = Unit.objects.create(book=book, number=1)
        u2 = Unit.objects.create(book=book, number=3)
        return GroupQuizSession.objects.create(
            chat_id=-100778, book=book, unit_ids=[u1.id, u2.id],
            question_count=15, interval_seconds=25, question_types=["en_uz"],
        )

    try:
        session = await sync_to_async(_setup)()
        text = await sync_to_async(group_quiz._config_text)(session)
        assert "B1" in text
        assert "1, 3" in text            # unit numbers
        assert "15 ta savol" in text
        assert "25 soniya" in text
    finally:
        await sync_to_async(connections.close_all)()


@patch("bot.handlers.group_quiz.asyncio.create_task")
@patch("bot.handlers.group_quiz.get_active_session")
async def test_go_quiz_launches_with_ready_people(mock_get_session, mock_create_task):
    """With ≥1 ready person the owner launches: countdown task scheduled, set cleared."""
    session = MagicMock()
    session.started_by_telegram_id = 111
    session.id = 9
    mock_get_session.return_value = session
    group_quiz._ready[9] = {5: "Ali"}

    callback = AsyncMock()
    callback.from_user.id = 111
    callback.message.chat.id = -100
    callback.message.message_id = 55
    callback.answer = AsyncMock()

    await group_quiz.go_quiz(callback)

    mock_create_task.assert_called_once()
    assert 9 not in group_quiz._ready

    # The scheduled coroutine was handed to the mocked create_task without
    # being awaited; close it so Python doesn't warn on GC.
    mock_create_task.call_args.args[0].close()
