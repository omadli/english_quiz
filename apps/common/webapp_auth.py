import time

from aiogram.utils.web_app import WebAppInitData, safe_parse_webapp_init_data
from django.conf import settings

_INIT_DATA_MAX_AGE = 86400  # seconds; reject stale/replayed initData


def parse_init_data(init_data: str) -> WebAppInitData | None:
    """Validate a Telegram Mini App `X-Telegram-Init-Data` header.
    Returns the parsed data, or None if it's absent, forged, stale or userless.

    Telegram's hash is computed over every field except `hash` — the newer
    `signature` field included (verified against a real tdesktop 9.6 client).
    aiogram keeps `signature` in its check string, so we pass initData through
    untouched. (An earlier version stripped `signature`, which rejected every
    real request — the hash no longer matched.)
    """
    if not init_data or not settings.BOT_TOKEN:
        return None
    try:
        data = safe_parse_webapp_init_data(token=settings.BOT_TOKEN, init_data=init_data)
    except ValueError:
        return None  # bad/forged signature
    if data.user is None or time.time() - data.auth_date.timestamp() > _INIT_DATA_MAX_AGE:
        return None
    return data
