import pytest

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit
from apps.learning.models import LearningProfile
from bot.services.users import (
    apply_wizard_data,
    get_or_create_user,
    set_starting_position,
    update_profile,
)

pytestmark = pytest.mark.django_db


def test_get_or_create_user_creates_everything():
    user, profile, created = get_or_create_user(
        telegram_id=555, username="ali", first_name="Ali", last_name="", language_code="uz"
    )
    assert created is True
    assert TelegramAccount.objects.get(telegram_id=555).user_id == user.id
    assert LearningProfile.objects.get(user=user).id == profile.id


def test_get_or_create_user_is_idempotent_and_updates_tg_fields():
    get_or_create_user(
        telegram_id=555, username="ali", first_name="Ali", last_name="", language_code="uz"
    )
    user, profile, created = get_or_create_user(
        telegram_id=555, username="ali2", first_name="Ali", last_name="V", language_code="en"
    )
    assert created is False
    assert User.objects.count() == 1
    assert TelegramAccount.objects.get(telegram_id=555).username == "ali2"


def test_set_starting_position_picks_first_book_and_unit():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    unit = Unit.objects.create(book=book, number=1)
    _, profile, _ = get_or_create_user(
        telegram_id=1, username="", first_name="A", last_name="", language_code=""
    )
    set_starting_position(profile)
    profile.refresh_from_db()
    assert profile.current_book_id == book.id
    assert profile.current_unit_id == unit.id
    assert profile.current_word_order == 0


def test_update_profile_sets_fields():
    _, profile, _ = get_or_create_user(
        telegram_id=3, username="", first_name="A", last_name="", language_code=""
    )
    update_profile(profile, words_per_session=20)
    profile.refresh_from_db()
    assert profile.words_per_session == 20


def test_apply_wizard_data_sets_fields_and_onboards():
    Book.objects.create(number=1, title="Book 1", slug="book-1")
    _, profile, _ = get_or_create_user(
        telegram_id=2, username="", first_name="A", last_name="", language_code=""
    )
    import datetime
    apply_wizard_data(profile, {
        "words_per_session": 15,
        "study_weekdays": [0, 2, 4],
        "morning_time": datetime.time(6, 30),
        "exam_time": datetime.time(21, 0),
        "audio_enabled": True,
        "audio_repeat": 3,
    })
    profile.refresh_from_db()
    assert profile.words_per_session == 15
    assert profile.study_weekdays == [0, 2, 4]
    assert profile.morning_time == datetime.time(6, 30)
    assert profile.audio_repeat == 3
    assert profile.onboarded is True
    assert profile.current_book is not None


def test_apply_wizard_data_does_not_reset_position_when_already_onboarded():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    Unit.objects.create(book=book, number=1)
    _, profile, _ = get_or_create_user(
        telegram_id=4, username="", first_name="A", last_name="", language_code=""
    )
    set_starting_position(profile)
    profile.current_word_order = 5
    profile.onboarded = True
    profile.save()

    apply_wizard_data(profile, {"words_per_session": 12})
    profile.refresh_from_db()

    assert profile.current_word_order == 5
    assert profile.words_per_session == 12
