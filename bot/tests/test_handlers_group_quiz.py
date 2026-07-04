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


@patch("bot.handlers.group_quiz.run_group_quiz")
@patch("bot.handlers.group_quiz.get_active_session")
async def test_start_quiz_rejects_non_owner(mock_get_session, mock_run):
    """A group member who did not start the wizard can't launch the quiz.

    `session.started_by_telegram_id` (111) differs from the tapping user
    (999), so `_owned_session` must reject the callback with an alert and
    `start_quiz` must never reach `run_group_quiz`/`asyncio.create_task`.
    """
    session = MagicMock()
    session.started_by_telegram_id = 111
    mock_get_session.return_value = session

    callback = AsyncMock()
    callback.from_user.id = 999
    callback.message.chat.id = -100
    callback.message.delete = AsyncMock()
    callback.answer = AsyncMock()

    await group_quiz.start_quiz(callback)

    mock_run.assert_not_called()
    callback.message.delete.assert_not_awaited()
    callback.answer.assert_awaited_with(group_quiz._NOT_OWNER, show_alert=True)


@patch("bot.handlers.group_quiz.asyncio.create_task")
@patch("bot.handlers.group_quiz.run_group_quiz", new_callable=AsyncMock)
@patch("bot.handlers.group_quiz.get_active_session")
async def test_start_quiz_allows_owner(mock_get_session, mock_run, mock_create_task):
    """The admin who started the wizard (matching `started_by_telegram_id`) can launch it."""
    session = MagicMock()
    session.started_by_telegram_id = 111
    session.id = 42
    mock_get_session.return_value = session

    callback = AsyncMock()
    callback.from_user.id = 111
    callback.message.chat.id = -100
    callback.message.delete = AsyncMock()
    callback.answer = AsyncMock()

    await group_quiz.start_quiz(callback)

    mock_run.assert_called_once_with(callback.bot, 42)
    callback.message.delete.assert_awaited_once()
    mock_create_task.assert_called_once()

    # `run_group_quiz(...)` (an AsyncMock) produced a real coroutine object
    # that was handed to the (mocked) `asyncio.create_task` without ever
    # being awaited or scheduled; close it explicitly so Python doesn't warn
    # "coroutine was never awaited" when it's garbage collected.
    launched_coro = mock_create_task.call_args.args[0]
    launched_coro.close()
