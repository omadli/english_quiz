from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import sync_to_async
from django.db import connections

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, LearningProfile, SessionWord
from apps.learning.services.deliver import today_session_words
from bot.handlers import daily

pytestmark = pytest.mark.asyncio


@patch("bot.handlers.daily._send_daily", new_callable=AsyncMock)
@patch("bot.handlers.daily.today_session_items")
async def test_menu_today_sends_session(mock_items, mock_send):
    mock_items.return_value = (b"card", [{"caption": "c", "image": None, "audio": None}])
    message = AsyncMock()
    message.chat.id = 555
    await daily.menu_today(message, user=MagicMock(id=1))
    mock_send.assert_awaited_once()


@patch("bot.handlers.daily.today_session_items", return_value=None)
async def test_menu_today_no_session_says_none(mock_items):
    message = AsyncMock()
    await daily.menu_today(message, user=MagicMock(id=1))
    said = [c.args[0] for c in message.answer.await_args_list if c.args]
    assert daily.strings.TODAY_NONE in said


@patch("bot.handlers.daily._countdown_then_run", new_callable=AsyncMock)
@patch("bot.handlers.daily.build_questions")
@patch("bot.handlers.daily.today_session_words")
async def test_menu_exam_runs_quiz_on_today_words(mock_words, mock_build, mock_run):
    mock_words.return_value = [MagicMock()]
    mock_build.return_value = [
        {"prompt": "a", "options": ["a", "b"], "correct_option": 0, "explanation": "x"}
    ]
    message = AsyncMock()
    message.chat.id = 555
    await daily.menu_exam(message, user=MagicMock(id=1))
    mock_run.assert_awaited_once()


@patch("bot.handlers.daily.today_session_words", return_value=[])
async def test_menu_exam_no_words_says_none(mock_words):
    message = AsyncMock()
    await daily.menu_exam(message, user=MagicMock(id=1))
    assert daily.strings.TODAY_NONE in message.answer.call_args.args


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_today_session_words_ordered():
    def _setup() -> int:
        user = User.objects.create(first_name="Ali")
        TelegramAccount.objects.create(user=user, telegram_id=555111)
        LearningProfile.objects.create(user=user)  # default tz
        book = Book.objects.create(number=1, title="B1", slug="b1-today")
        unit = Unit.objects.create(book=book, number=1)
        w1 = Word.objects.create(unit=unit, en="a", uz="a", order=1)
        w2 = Word.objects.create(unit=unit, en="b", uz="b", order=2)
        from zoneinfo import ZoneInfo

        from django.utils import timezone
        today = timezone.now().astimezone(ZoneInfo("Asia/Tashkent")).date()
        session = DailySession.objects.create(user=user, date=today)
        SessionWord.objects.create(daily_session=session, word=w2, order=2)
        SessionWord.objects.create(daily_session=session, word=w1, order=1)
        return user.id

    try:
        user_id = await sync_to_async(_setup)()
        words = await sync_to_async(today_session_words)(user_id)
        assert [w.en for w in words] == ["a", "b"]  # ordered by SessionWord.order
    finally:
        await sync_to_async(connections.close_all)()
