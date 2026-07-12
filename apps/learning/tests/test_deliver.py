from unittest.mock import MagicMock, patch

import pytest
from aiogram.exceptions import TelegramForbiddenError

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, LearningProfile, WordProgress
from apps.learning.services import deliver as deliver_mod

pytestmark = pytest.mark.django_db


@pytest.fixture
def user_with_words():
    user = User.objects.create(first_name="T")
    TelegramAccount.objects.create(user=user, telegram_id=555)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    for i in range(1, 6):
        Word.objects.create(unit=unit, en=f"w{i}", uz=f"t{i}", order=i)
    LearningProfile.objects.create(
        user=user, onboarded=True, words_per_session=3,
        current_book=book, current_unit=unit, current_word_order=0,
    )
    return user, book, unit


@patch("apps.learning.services.deliver.send_daily")
@patch("apps.learning.services.deliver.build_daily_audio", return_value=b"AUD")
def test_run_delivery_sends_one_audio_and_caption(mock_audio, mock_send, user_with_words):
    user, book, unit = user_with_words
    session = deliver_mod.run_delivery(user.id)
    assert session.status == DailySession.Status.DELIVERED
    assert list(session.words.values_list("en", flat=True)) == ["w1", "w2", "w3"]
    assert WordProgress.objects.filter(user=user).count() == 3
    mock_audio.assert_called_once()  # ONE combined audio, not one-per-word
    mock_send.assert_called_once()
    _chat, caption, audio, _webapp = mock_send.call_args.args
    assert audio == b"AUD"
    assert "w1" in caption and "w2" in caption and "w3" in caption  # list caption
    user.learning_profile.refresh_from_db()
    assert user.learning_profile.current_word_order == 3  # advanced to last delivered


@patch("apps.learning.services.deliver.send_daily")
@patch("apps.learning.services.deliver.build_daily_audio", return_value=b"AUD")
def test_run_delivery_idempotent(mock_audio, mock_send, user_with_words):
    user, *_ = user_with_words
    deliver_mod.run_delivery(user.id)
    mock_send.reset_mock()
    assert deliver_mod.run_delivery(user.id) is None
    mock_send.assert_not_called()
    assert DailySession.objects.filter(user=user).count() == 1


@patch("apps.learning.services.deliver.send_daily")
def test_run_delivery_no_content(mock_send, user_with_words):
    user, *_ = user_with_words
    p = user.learning_profile
    p.current_word_order = 5  # past the last word
    p.save()
    assert deliver_mod.run_delivery(user.id) is None
    mock_send.assert_not_called()


@patch("apps.learning.services.deliver.send_daily",
       side_effect=TelegramForbiddenError(method=MagicMock(), message="blocked"))
@patch("apps.learning.services.deliver.build_daily_audio", return_value=b"AUD")
def test_run_delivery_blocked(mock_audio, mock_send, user_with_words):
    user, *_ = user_with_words
    assert deliver_mod.run_delivery(user.id) is None
    user.telegram.refresh_from_db()
    assert user.telegram.blocked_bot is True
    user.learning_profile.refresh_from_db()
    assert user.learning_profile.current_word_order == 0
    assert DailySession.objects.filter(user=user, status=DailySession.Status.PENDING).exists()
