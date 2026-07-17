import re
import time

from aiogram.utils.web_app import WebAppInitData, safe_parse_webapp_init_data
from django.conf import settings

_INIT_DATA_MAX_AGE = 86400  # seconds; reject stale/replayed initData

# Telegram signs initData over every field except `hash` AND `signature`, but
# aiogram (still, as of 3.29) folds `signature` into its check string — so every
# real Mini App request fails validation. Drop the pair from the raw query
# string; no parse/re-encode, since the HMAC covers the exact bytes Telegram sent.
_SIGNATURE_RE = re.compile(r"(?:^|&)signature=[^&]*")


def parse_init_data(init_data: str) -> WebAppInitData | None:
    """Validate a Telegram Mini App `X-Telegram-Init-Data` header.
    Returns the parsed data, or None if it's absent, forged, stale or userless."""
    if not init_data or not settings.BOT_TOKEN:
        return None
    cleaned = _SIGNATURE_RE.sub("", init_data).lstrip("&")
    try:
        data = safe_parse_webapp_init_data(token=settings.BOT_TOKEN, init_data=cleaned)
    except ValueError:
        return None  # bad/forged signature
    if data.user is None or time.time() - data.auth_date.timestamp() > _INIT_DATA_MAX_AGE:
        return None
    return data
