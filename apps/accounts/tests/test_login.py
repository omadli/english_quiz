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


def _user(tg_id=555, active=True):
    user = User.objects.create(first_name="Ali", is_active=active)
    TelegramAccount.objects.create(user=user, telegram_id=tg_id)
    return user


# ---- create_login_request ---------------------------------------------------
def test_create_login_request_makes_open_row():
    nonce = svc.create_login_request()
    assert len(nonce) > 20
    entry = LoginCode.objects.get(nonce=nonce)
    assert entry.user_id is None and entry.code == "" and entry.used is False


# ---- fulfill_login_request (bot side) ---------------------------------------
def test_fulfill_attaches_user_and_code():
    user = _user()
    nonce = svc.create_login_request()
    code = svc.fulfill_login_request(nonce, user)
    assert len(code) == 6
    entry = LoginCode.objects.get(nonce=nonce)
    assert entry.user == user and entry.code == code


def test_fulfill_unknown_nonce_returns_none():
    assert svc.fulfill_login_request("nope", _user()) is None


def test_fulfill_expired_nonce_returns_none():
    user = _user()
    nonce = svc.create_login_request()
    LoginCode.objects.filter(nonce=nonce).update(expires_at=timezone.now() - timedelta(minutes=1))
    assert svc.fulfill_login_request(nonce, user) is None


# ---- verify_login_request (browser side) ------------------------------------
def _fulfilled(user, code="123456"):
    nonce = svc.create_login_request()
    LoginCode.objects.filter(nonce=nonce).update(user=user, code=code)
    return nonce


def test_verify_correct_returns_user_and_burns_request():
    user = _user()
    nonce = _fulfilled(user, "123456")
    assert svc.verify_login_request(nonce, "123456") == user
    assert LoginCode.objects.get(nonce=nonce).used is True


def test_verify_before_bot_fulfilled_returns_none():
    # nonce exists but the user hasn't opened the bot yet (no user/code)
    nonce = svc.create_login_request()
    assert svc.verify_login_request(nonce, "123456") is None


def test_verify_wrong_increments_attempts():
    user = _user()
    nonce = _fulfilled(user, "123456")
    assert svc.verify_login_request(nonce, "000000") is None
    assert LoginCode.objects.get(nonce=nonce).attempts == 1


def test_verify_expired_returns_none():
    user = _user()
    nonce = _fulfilled(user, "123456")
    LoginCode.objects.filter(nonce=nonce).update(expires_at=timezone.now() - timedelta(minutes=1))
    assert svc.verify_login_request(nonce, "123456") is None


def test_verify_attempts_cap_locks_request():
    user = _user()
    nonce = _fulfilled(user, "123456")
    LoginCode.objects.filter(nonce=nonce).update(attempts=5)
    assert svc.verify_login_request(nonce, "123456") is None  # correct code but capped
    assert LoginCode.objects.get(nonce=nonce).used is True


def test_verify_inactive_user_denied():
    user = _user(active=False)
    nonce = _fulfilled(user, "123456")
    assert svc.verify_login_request(nonce, "123456") is None


# ---- views ------------------------------------------------------------------
def test_dashboard_requires_login(client):
    resp = client.get("/app/")
    assert resp.status_code == 302
    assert "/login/" in resp.url


def test_logout_rejects_get(client):
    assert client.get("/logout/").status_code == 405


def test_login_page_renders_and_sets_csrf_cookie(client):
    resp = client.get("/login/")
    assert resp.status_code == 200
    assert "csrftoken" in resp.cookies


def test_login_link_returns_deeplink(client, settings):
    settings.BOT_USERNAME = "learn_englishuz_bot"
    resp = client.post("/app/api/login-link/")
    d = resp.json()
    assert d["ok"] and d["url"].startswith("https://t.me/learn_englishuz_bot?start=login_")
    assert LoginCode.objects.filter(nonce=d["nonce"]).exists()


def test_login_link_without_bot_username(client, settings):
    settings.BOT_USERNAME = ""
    assert client.post("/app/api/login-link/").status_code == 503


def test_verify_code_view_logs_in_and_dashboard_opens(client):
    user = _user()
    nonce = _fulfilled(user, "123456")
    resp = client.post(
        "/app/api/verify-code/",
        data=json.dumps({"nonce": nonce, "code": "123456"}),
        content_type="application/json",
    )
    assert resp.json() == {"ok": True, "redirect": "/app/"}
    assert client.get("/app/").status_code == 200


def test_verify_code_view_rejects_bad_code(client):
    user = _user()
    nonce = _fulfilled(user, "123456")
    resp = client.post(
        "/app/api/verify-code/",
        data=json.dumps({"nonce": nonce, "code": "999999"}),
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert client.get("/app/").status_code == 302  # still not logged in


# ---- Telegram in-app auto-login (initData) — unchanged ----------------------
def _init_data(user: dict, token: str = TOKEN) -> str:
    fields = {"auth_date": str(int(time.time())), "user": json.dumps(user, separators=(",", ":"))}
    fields["signature"] = "abc123"  # real clients send it; Telegram folds it into the hash
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
