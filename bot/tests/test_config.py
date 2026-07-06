import pytest

from bot.config import get_bot_mode, get_bot_token, get_fsm_redis_url, get_webhook_config


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


def test_get_bot_mode_defaults_to_polling(settings):
    settings.BOT_MODE = "anything-else"
    assert get_bot_mode() == "polling"
    settings.BOT_MODE = "webhook"
    assert get_bot_mode() == "webhook"


def test_get_webhook_config_derives_path(settings):
    settings.WEBHOOK_URL = "https://bot.example.com/tg/hook"
    settings.WEBHOOK_SECRET = "s3cret"
    settings.WEBHOOK_PORT = 9090
    cfg = get_webhook_config()
    assert cfg["path"] == "/tg/hook"
    assert cfg["url"] == "https://bot.example.com/tg/hook"
    assert cfg["secret"] == "s3cret"
    assert cfg["port"] == 9090


def test_get_webhook_config_raises_without_url(settings):
    settings.WEBHOOK_URL = ""
    with pytest.raises(RuntimeError):
        get_webhook_config()
