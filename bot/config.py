import re

from django.conf import settings


def get_bot_token() -> str:
    token = settings.BOT_TOKEN
    if not token:
        raise RuntimeError("BOT_TOKEN is not set — put it in .env")
    return token


def get_fsm_redis_url() -> str:
    """Return REDIS_URL with its DB index forced to 2 (dedicated FSM DB)."""
    url = settings.REDIS_URL
    if re.search(r"/\d+$", url):
        return re.sub(r"/\d+$", "/2", url)
    return url.rstrip("/") + "/2"
