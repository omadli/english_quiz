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


def _init_data(
    user: dict, auth_date: int | None = None, token: str = TOKEN, signature: str = "abc123"
) -> str:
    """Build a signed Telegram WebApp initData string, mirroring a REAL client.

    Telegram computes the hash over every field except `hash` — the `signature`
    field INCLUDED (confirmed against a live tdesktop 9.6: hash validated only
    with signature in the check string). So `signature` is added *before* the
    hash is computed, exactly as Telegram's servers do."""
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "user": json.dumps(user, separators=(",", ":")),
    }
    if signature:
        fields["signature"] = signature
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


def test_profile_accepts_init_data_without_signature(client, settings):
    settings.BOT_TOKEN = TOKEN  # older clients omit it; stripping must not break them
    _user(555)
    resp = client.get(
        "/webapp/api/profile/",
        HTTP_X_TELEGRAM_INIT_DATA=_init_data({"id": 555, "first_name": "Ali"}, signature=""),
    )
    assert resp.status_code == 200


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


def test_profile_returns_voices_and_updates(client, settings):
    settings.BOT_TOKEN = TOKEN
    user = _user(555)
    auth = _init_data({"id": 555, "first_name": "Ali"})
    got = client.get("/webapp/api/profile/", HTTP_X_TELEGRAM_INIT_DATA=auth).json()
    assert got["en_voice"] == "en-US-AriaNeural"
    assert any(v[0] == "uz-UZ-SardorNeural" for v in got["uz_voices"])  # catalog exposed
    # POST: valid voice sticks, invalid one is dropped
    client.post(
        "/webapp/api/profile/",
        data=json.dumps({"en_voice": "en-US-GuyNeural", "uz_voice": "bogus"}),
        content_type="application/json", HTTP_X_TELEGRAM_INIT_DATA=auth,
    )
    p = LearningProfile.objects.get(user=user)
    assert p.en_voice == "en-US-GuyNeural"
    assert p.uz_voice == "uz-UZ-MadinaNeural"  # bogus rejected, default kept


def _word() -> Word:
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    return Word.objects.create(unit=unit, en="afraid", uz="qo'rqqan", order=1)


def test_learned_requires_auth(client, settings):
    settings.BOT_TOKEN = TOKEN
    assert client.get("/webapp/api/learned/").status_code == 401


def test_learned_get_lists_ids_and_reflects_in_profile(client, settings):
    settings.BOT_TOKEN = TOKEN
    user = _user(555)
    word = _word()
    LearnedWord.objects.create(user=user, word=word)  # earned via a test, marked bot-side
    auth = _init_data({"id": 555, "first_name": "Ali"})

    listed = client.get("/webapp/api/learned/", HTTP_X_TELEGRAM_INIT_DATA=auth)
    assert listed.json()["ids"] == [word.id]

    prof = client.get("/webapp/api/profile/", HTTP_X_TELEGRAM_INIT_DATA=auth)
    assert prof.json()["learned_words"] == 1


def test_api_units_includes_learned_counts_when_authed(client, settings):
    settings.BOT_TOKEN = TOKEN
    user = _user(555)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    u1 = Unit.objects.create(book=book, number=1, word_count=2)
    u2 = Unit.objects.create(book=book, number=2, word_count=2)
    w1 = Word.objects.create(unit=u1, en="a", uz="a", order=1)
    Word.objects.create(unit=u1, en="b", uz="b", order=2)
    Word.objects.create(unit=u2, en="c", uz="c", order=1)
    LearnedWord.objects.create(user=user, word=w1)  # 1 of unit 1 learned

    resp = client.get(
        f"/webapp/api/units/{book.id}/",
        HTTP_X_TELEGRAM_INIT_DATA=_init_data({"id": 555, "first_name": "Ali"}),
    )
    units = {u["number"]: u for u in resp.json()["units"]}
    assert units[1]["learned"] == 1
    assert units[2]["learned"] == 0


def test_api_units_no_learned_key_without_auth(client):
    book = Book.objects.create(number=1, title="B1", slug="b1")
    Unit.objects.create(book=book, number=1, word_count=2)
    resp = client.get(f"/webapp/api/units/{book.id}/")
    assert "learned" not in resp.json()["units"][0]  # anonymous → no per-user data


def test_api_today_requires_auth(client, settings):
    settings.BOT_TOKEN = TOKEN
    assert client.get("/webapp/api/today/").status_code == 401


def test_api_today_returns_ordered_session_words(client, settings):
    from zoneinfo import ZoneInfo

    from django.utils import timezone

    from apps.learning.models import DailySession, LearningProfile, SessionWord

    settings.BOT_TOKEN = TOKEN
    user = _user(555)
    profile = LearningProfile.objects.create(user=user)  # default tz Asia/Tashkent
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    w1 = Word.objects.create(unit=unit, en="a", uz="a", order=1)
    w2 = Word.objects.create(unit=unit, en="b", uz="b", order=2)
    today = timezone.now().astimezone(ZoneInfo(profile.timezone)).date()
    session = DailySession.objects.create(user=user, date=today)
    SessionWord.objects.create(daily_session=session, word=w2, order=2)  # inserted out of order
    SessionWord.objects.create(daily_session=session, word=w1, order=1)

    resp = client.get(
        "/webapp/api/today/", HTTP_X_TELEGRAM_INIT_DATA=_init_data({"id": 555, "first_name": "Ali"})
    )
    data = resp.json()
    assert [w["en"] for w in data["words"]] == ["a", "b"]  # ordered by SessionWord.order


def test_api_today_empty_without_session(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user(555)
    resp = client.get(
        "/webapp/api/today/", HTTP_X_TELEGRAM_INIT_DATA=_init_data({"id": 555, "first_name": "Ali"})
    )
    assert resp.json() == {"words": [], "status": "none"}


def test_learned_has_no_manual_post(client, settings):
    """Manual marking was removed — POST must not create a LearnedWord."""
    settings.BOT_TOKEN = TOKEN
    user = _user(555)
    word = _word()
    client.post(
        "/webapp/api/learned/", data=json.dumps({"word_id": word.id, "learned": True}),
        content_type="application/json",
        HTTP_X_TELEGRAM_INIT_DATA=_init_data({"id": 555, "first_name": "Ali"}),
    )
    assert not LearnedWord.objects.filter(user=user, word=word).exists()
