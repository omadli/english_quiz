import pytest

from bot.config import get_bot_token, get_fsm_redis_url


def test_get_fsm_redis_url_replaces_db_index(settings):
    settings.REDIS_URL = "redis://redis:6379/1"
    assert get_fsm_redis_url() == "redis://redis:6379/2"


def test_get_fsm_redis_url_appends_when_no_index(settings):
    settings.REDIS_URL = "redis://redis:6379"
    assert get_fsm_redis_url() == "redis://redis:6379/2"


def test_get_bot_token_raises_when_empty(settings):
    settings.BOT_TOKEN = ""
    with pytest.raises(RuntimeError):
        get_bot_token()


def test_get_bot_token_returns_value(settings):
    settings.BOT_TOKEN = "123:abc"
    assert get_bot_token() == "123:abc"
