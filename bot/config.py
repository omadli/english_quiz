import re
from urllib.parse import urlparse

from django.conf import settings


def get_bot_token() -> str:
    token = settings.BOT_TOKEN
    if not token:
        raise RuntimeError("BOT_TOKEN is not set — put it in .env")
    return token


def get_bot_mode() -> str:
    return "webhook" if settings.BOT_MODE == "webhook" else "polling"


def get_webhook_config() -> dict:
    """URL to register with Telegram + the local path/port to listen on."""
    url = settings.WEBHOOK_URL
    if not url:
        raise RuntimeError("WEBHOOK_URL is not set — required for BOT_MODE=webhook")
    return {
        "url": url,
        "path": urlparse(url).path or "/webhook",
        "secret": settings.WEBHOOK_SECRET or None,
        "port": settings.WEBHOOK_PORT,
    }


def get_fsm_redis_url() -> str:
    """Return REDIS_URL with its DB index forced to 2 (dedicated FSM DB)."""
    url = settings.REDIS_URL
    if re.search(r"/\d+$", url):
        return re.sub(r"/\d+$", "/2", url)
    return url.rstrip("/") + "/2"
