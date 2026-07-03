import pytest

from apps.accounts.models import TelegramAccount, User

pytestmark = pytest.mark.django_db


def test_user_can_be_created_without_phone():
    user = User.objects.create(first_name="Ali")
    assert user.phone_number is None
    assert user.full_name == "Ali"


def test_full_name_includes_last_name():
    user = User.objects.create(first_name="Ali", last_name="Valiyev")
    assert user.full_name == "Ali Valiyev"


def test_create_user_manager_requires_phone():
    with pytest.raises(ValueError):
        User.objects.create_user(first_name="Ali", phone_number=None, password="x")


def test_telegram_account_links_to_user():
    user = User.objects.create(first_name="Ali")
    tg = TelegramAccount.objects.create(user=user, telegram_id=12345, username="ali")
    assert user.telegram.telegram_id == 12345
    assert str(tg) == "@ali"
