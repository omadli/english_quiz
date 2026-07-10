import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import LoginCode, TelegramAccount, User

CODE_TTL = timedelta(minutes=5)
RESEND_THROTTLE = timedelta(seconds=60)
MAX_ATTEMPTS = 5


def resolve_account(identifier: str) -> TelegramAccount | None:
    """Find the Telegram account for a login identifier (@username, or phone digits).

    Username is the reliable path — phone is rarely set on bot-created users, so
    it's a best-effort fallback. Callers should show a clear dead-end when this
    returns None (the user can always sign in from inside Telegram via initData).
    """
    ident = (identifier or "").strip().lstrip("@")
    if not ident:
        return None
    account = TelegramAccount.objects.select_related("user").filter(username__iexact=ident).first()
    if account is None and ident.isdigit():
        user = User.objects.filter(phone_number=int(ident)).first()
        account = getattr(user, "telegram", None) if user else None
    return account


def _send_code_dm(telegram_id: int, code: str) -> bool:
    token = settings.BOT_TOKEN
    if not token:
        return False
    text = f"🔐 Kirish kodingiz: <b>{code}</b>\n\n5 daqiqa amal qiladi. Hech kimga bermang."
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": telegram_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def request_login_code(identifier: str) -> dict:
    """Generate a code and DM it. Returns {'ok': bool, 'error': <reason>}."""
    account = resolve_account(identifier)
    if account is None:
        return {"ok": False, "error": "not_found"}
    user = account.user
    if not user.is_active:
        return {"ok": False, "error": "not_found"}
    if LoginCode.objects.filter(
        user=user, created_at__gte=timezone.now() - RESEND_THROTTLE
    ).exists():
        return {"ok": False, "error": "throttled"}
    LoginCode.objects.filter(user=user, used=False).update(used=True)  # invalidate older codes
    code = f"{secrets.randbelow(1_000_000):06d}"
    entry = LoginCode.objects.create(user=user, code=code, expires_at=timezone.now() + CODE_TTL)
    if not _send_code_dm(account.telegram_id, code):
        entry.delete()  # let the user retry immediately if the DM failed
        return {"ok": False, "error": "send_failed"}
    return {"ok": True}


def verify_login_code(identifier: str, code: str) -> User | None:
    account = resolve_account(identifier)
    if account is None:
        return None
    entry = (
        LoginCode.objects.filter(user=account.user, used=False, expires_at__gte=timezone.now())
        .order_by("-created_at")
        .first()
    )
    if entry is None:
        return None
    if entry.attempts >= MAX_ATTEMPTS:
        entry.used = True
        entry.save(update_fields=["used"])
        return None
    if not secrets.compare_digest(entry.code, (code or "").strip()):
        entry.attempts += 1
        entry.save(update_fields=["attempts"])
        return None
    entry.used = True
    entry.save(update_fields=["used"])
    return account.user if account.user.is_active else None
