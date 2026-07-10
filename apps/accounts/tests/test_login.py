import hashlib
import hmac
import json
import time
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.utils import timezone

from apps.accounts.models import LoginCode, TelegramAccount, User
from apps.accounts.services import login as svc

TOKEN = "123:TESTTOKEN"
pytestmark = pytest.mark.django_db


def _user(username="ali", tg_id=555, phone=None, active=True):
    user = User.objects.create(first_name="Ali", phone_number=phone, is_active=active)
    TelegramAccount.objects.create(user=user, telegram_id=tg_id, username=username)
    return user


# ---- resolve_account --------------------------------------------------------
def test_resolve_by_username_case_insensitive_and_at_prefix():
    _user(username="Ali")
    assert svc.resolve_account("@ali").username == "Ali"
    assert svc.resolve_account("ALI").username == "Ali"


def test_resolve_by_phone_digits():
    _user(username="", tg_id=7, phone=998901234567)
    assert svc.resolve_account("998901234567").telegram_id == 7


def test_resolve_unknown_returns_none():
    assert svc.resolve_account("nobody") is None
    assert svc.resolve_account("") is None


def test_resolve_overlong_digits_no_crash():
    # a 25-digit "phone" would overflow bigint → must be skipped, not raise DataError
    assert svc.resolve_account("9" * 25) is None


# ---- request_login_code -----------------------------------------------------
def test_request_code_success_creates_and_sends(monkeypatch):
    _user()
    sent = {}

    def _capture(tg, code):
        sent["code"] = code
        return True

    monkeypatch.setattr(svc, "_send_code_dm", _capture)
    res = svc.request_login_code("ali")
    assert res == {"ok": True}
    assert LoginCode.objects.filter(used=False).count() == 1
    assert len(sent["code"]) == 6


def test_request_code_not_found():
    assert svc.request_login_code("ghost") == {"ok": False, "error": "not_found"}


def test_request_code_throttled(monkeypatch):
    user = _user()
    monkeypatch.setattr(svc, "_send_code_dm", lambda tg, code: True)
    _code_for(user, "000000")
    assert svc.request_login_code("ali") == {"ok": False, "error": "throttled"}


def test_request_code_send_failure_deletes_row(monkeypatch):
    _user()
    monkeypatch.setattr(svc, "_send_code_dm", lambda tg, code: False)
    assert svc.request_login_code("ali") == {"ok": False, "error": "send_failed"}
    assert LoginCode.objects.count() == 0  # rolled back so the user can retry


# ---- verify_login_code ------------------------------------------------------
def _code_for(user, code="123456", **kw):
    kw.setdefault("expires_at", timezone.now() + timedelta(minutes=5))
    return LoginCode.objects.create(user=user, code=code, **kw)


def test_verify_correct_returns_user_and_consumes_code():
    user = _user()
    _code_for(user, "123456")
    assert svc.verify_login_code("ali", "123456") == user
    assert LoginCode.objects.get(user=user).used is True


def test_verify_wrong_increments_attempts():
    user = _user()
    _code_for(user, "123456")
    assert svc.verify_login_code("ali", "000000") is None
    assert LoginCode.objects.get(user=user).attempts == 1


def test_verify_expired_returns_none():
    user = _user()
    _code_for(user, "123456", expires_at=timezone.now() - timedelta(minutes=1))
    assert svc.verify_login_code("ali", "123456") is None


def test_verify_attempts_cap_locks_code():
    user = _user()
    _code_for(user, "123456", attempts=5)
    assert svc.verify_login_code("ali", "123456") is None  # correct code but capped
    assert LoginCode.objects.get(user=user).used is True


def test_verify_inactive_user_denied():
    user = _user(active=False)
    _code_for(user, "123456")
    assert svc.verify_login_code("ali", "123456") is None


# ---- views ------------------------------------------------------------------
def test_dashboard_requires_login(client):
    resp = client.get("/app/")
    assert resp.status_code == 302
    assert "/login/" in resp.url


def test_logout_rejects_get(client):
    # logout must be POST-only (a GET <img src> must not log users out)
    assert client.get("/logout/").status_code == 405


def test_login_page_renders_and_sets_csrf_cookie(client):
    resp = client.get("/login/")
    assert resp.status_code == 200
    assert "csrftoken" in resp.cookies


def test_verify_code_view_logs_in_and_dashboard_opens(client, monkeypatch):
    user = _user()
    _code_for(user, "123456")
    resp = client.post(
        "/app/api/verify-code/",
        data=json.dumps({"identifier": "ali", "code": "123456"}),
        content_type="application/json",
    )
    assert resp.json() == {"ok": True, "redirect": "/app/"}
    assert client.get("/app/").status_code == 200  # session now authenticated


def test_verify_code_view_rejects_bad_code(client):
    user = _user()
    _code_for(user, "123456")
    resp = client.post(
        "/app/api/verify-code/",
        data=json.dumps({"identifier": "ali", "code": "999999"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert client.get("/app/").status_code == 302  # still not logged in


def _init_data(user: dict, token: str = TOKEN) -> str:
    fields = {"auth_date": str(int(time.time())), "user": json.dumps(user, separators=(",", ":"))}
    dcs = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_session_init_logs_in_via_valid_init_data(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user(tg_id=555)
    resp = client.post(
        "/app/api/session/",
        data=json.dumps({"init_data": _init_data({"id": 555, "first_name": "Ali"})}),
        content_type="application/json",
    )
    assert resp.json()["ok"] is True
    assert client.get("/app/").status_code == 200


def test_session_init_rejects_forged(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user(tg_id=555)
    forged = _init_data({"id": 555, "first_name": "Ali"}, token="attacker")
    resp = client.post(
        "/app/api/session/",
        data=json.dumps({"init_data": forged}),
        content_type="application/json",
    )
    assert resp.status_code == 401
