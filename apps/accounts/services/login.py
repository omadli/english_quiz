import secrets
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import LoginCode, User

LINK_TTL = timedelta(minutes=10)  # how long a login deep link stays openable
MAX_ATTEMPTS = 5


def create_login_request() -> str:
    """Browser side: mint a nonce for a login attempt and return it. The user
    then opens t.me/bot?start=login_<nonce>."""
    nonce = secrets.token_urlsafe(24)
    LoginCode.objects.create(nonce=nonce, expires_at=timezone.now() + LINK_TTL)
    return nonce


def _open_request(nonce: str) -> LoginCode | None:
    return LoginCode.objects.filter(
        nonce=nonce, used=False, expires_at__gte=timezone.now()
    ).first()


def fulfill_login_request(nonce: str, user: User) -> str | None:
    """Bot side: the user opened the login deep link. Attach their account and a
    fresh one-time code to the pending request; return the code for the bot to DM.
    Returns None if the nonce is unknown, used, or expired."""
    entry = _open_request(nonce)
    if entry is None:
        return None
    code = f"{secrets.randbelow(1_000_000):06d}"
    entry.user = user
    entry.code = code
    entry.save(update_fields=["user", "code", "updated_at"])
    return code


def verify_login_request(nonce: str, code: str) -> User | None:
    """Browser side: the user typed the code. Returns the user on success (and
    burns the request), None otherwise."""
    entry = _open_request(nonce)
    if entry is None or entry.user_id is None or not entry.code:
        return None
    if entry.attempts >= MAX_ATTEMPTS:
        entry.used = True
        entry.save(update_fields=["used", "updated_at"])
        return None
    if not secrets.compare_digest(entry.code, (code or "").strip()):
        entry.attempts += 1
        entry.save(update_fields=["attempts", "updated_at"])
        return None
    entry.used = True
    entry.save(update_fields=["used", "updated_at"])
    return entry.user if entry.user.is_active else None
