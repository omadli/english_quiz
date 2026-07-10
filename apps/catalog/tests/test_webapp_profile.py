import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import LearnedWord, LearningProfile

TOKEN = "123:TESTTOKEN"
pytestmark = pytest.mark.django_db


def _init_data(user: dict, auth_date: int | None = None, token: str = TOKEN) -> str:
    """Build a signed Telegram WebApp initData string (mirrors the client)."""
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "user": json.dumps(user, separators=(",", ":")),
    }
    dcs = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def _user(tg_id: int = 555) -> User:
    user = User.objects.create(first_name="Ali")
    TelegramAccount.objects.create(user=user, telegram_id=tg_id)
    return user


def test_profile_requires_init_data(client, settings):
    settings.BOT_TOKEN = TOKEN
    assert client.get("/webapp/api/profile/").status_code == 401


def test_profile_rejects_forged_signature(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user(555)
    forged = _init_data({"id": 555, "first_name": "Ali"}, token="attacker-token")
    resp = client.get("/webapp/api/profile/", HTTP_X_TELEGRAM_INIT_DATA=forged)
    assert resp.status_code == 401


def test_profile_rejects_stale_init_data(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user(555)
    old = _init_data({"id": 555, "first_name": "Ali"}, auth_date=int(time.time()) - 100_000)  # >24h
    resp = client.get("/webapp/api/profile/", HTTP_X_TELEGRAM_INIT_DATA=old)
    assert resp.status_code == 401


def test_profile_unknown_user_unauthorized(client, settings):
    settings.BOT_TOKEN = TOKEN  # valid signature but no TelegramAccount for id 999
    resp = client.get(
        "/webapp/api/profile/", HTTP_X_TELEGRAM_INIT_DATA=_init_data({"id": 999, "first_name": "X"})
    )
    assert resp.status_code == 401


def test_profile_get_returns_settings_and_progress(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user(555)
    resp = client.get(
        "/webapp/api/profile/",
        HTTP_X_TELEGRAM_INIT_DATA=_init_data({"id": 555, "first_name": "Ali"}),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["words_per_session"] == 10
    assert data["morning_time"] == "07:00"
    assert data["learned_words"] == 0


def test_profile_post_updates_editable_fields(client, settings):
    settings.BOT_TOKEN = TOKEN
    user = _user(555)
    body = {
        "words_per_session": 20,
        "morning_time": "06:30",
        "study_weekdays": [0, 1, 2],
        "audio_enabled": False,
        "audio_repeat": 3,
    }
    resp = client.post(
        "/webapp/api/profile/",
        data=json.dumps(body),
        content_type="application/json",
        HTTP_X_TELEGRAM_INIT_DATA=_init_data({"id": 555, "first_name": "Ali"}),
    )
    assert resp.status_code == 200
    p = LearningProfile.objects.get(user=user)
    assert p.words_per_session == 20
    assert p.morning_time.strftime("%H:%M") == "06:30"
    assert p.study_weekdays == [0, 1, 2]
    assert p.audio_enabled is False
    assert p.audio_repeat == 3


def test_profile_post_drops_invalid_values(client, settings):
    settings.BOT_TOKEN = TOKEN
    user = _user(555)
    body = {"words_per_session": 9999, "morning_time": "25:99", "study_weekdays": [0, 1, 9, "x"]}
    resp = client.post(
        "/webapp/api/profile/",
        data=json.dumps(body),
        content_type="application/json",
        HTTP_X_TELEGRAM_INIT_DATA=_init_data({"id": 555, "first_name": "Ali"}),
    )
    assert resp.status_code == 200
    p = LearningProfile.objects.get(user=user)
    assert p.words_per_session == 10                 # out-of-range dropped
    assert p.morning_time.strftime("%H:%M") == "07:00"  # bad time dropped
    assert p.study_weekdays == [0, 1]                # invalid days filtered out


def _word() -> Word:
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    return Word.objects.create(unit=unit, en="afraid", uz="qo'rqqan", order=1)


def test_learned_requires_auth(client, settings):
    settings.BOT_TOKEN = TOKEN
    assert client.get("/webapp/api/learned/").status_code == 401


def test_learned_toggle_on_then_off(client, settings):
    settings.BOT_TOKEN = TOKEN
    user = _user(555)
    word = _word()
    auth = _init_data({"id": 555, "first_name": "Ali"})

    on = client.post(
        "/webapp/api/learned/", data=json.dumps({"word_id": word.id, "learned": True}),
        content_type="application/json", HTTP_X_TELEGRAM_INIT_DATA=auth,
    )
    assert on.status_code == 200
    assert on.json()["ids"] == [word.id]
    assert LearnedWord.objects.filter(user=user, word=word).exists()

    off = client.post(
        "/webapp/api/learned/", data=json.dumps({"word_id": word.id, "learned": False}),
        content_type="application/json", HTTP_X_TELEGRAM_INIT_DATA=auth,
    )
    assert off.json()["ids"] == []
    assert not LearnedWord.objects.filter(user=user, word=word).exists()


def test_learned_get_lists_ids_and_reflects_in_profile(client, settings):
    settings.BOT_TOKEN = TOKEN
    user = _user(555)
    word = _word()
    LearnedWord.objects.create(user=user, word=word)
    auth = _init_data({"id": 555, "first_name": "Ali"})

    listed = client.get("/webapp/api/learned/", HTTP_X_TELEGRAM_INIT_DATA=auth)
    assert listed.json()["ids"] == [word.id]

    prof = client.get("/webapp/api/profile/", HTTP_X_TELEGRAM_INIT_DATA=auth)
    assert prof.json()["learned_words"] == 1


def test_learned_rejects_unknown_word(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user(555)
    resp = client.post(
        "/webapp/api/learned/", data=json.dumps({"word_id": 999999, "learned": True}),
        content_type="application/json",
        HTTP_X_TELEGRAM_INIT_DATA=_init_data({"id": 555, "first_name": "Ali"}),
    )
    assert resp.status_code == 400
