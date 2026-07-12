import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from apps.accounts.models import TelegramAccount, User
from apps.learning.models import LearningProfile
from apps.relations.models import Guardianship

TOKEN = "123:TESTTOKEN"
pytestmark = pytest.mark.django_db


def _init_data(uid: int) -> str:
    fields = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": uid, "first_name": "G"}, separators=(",", ":")),
    }
    dcs = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def _guardian_ward():
    guardian = User.objects.create(first_name="Mom")
    TelegramAccount.objects.create(user=guardian, telegram_id=700)
    learner = User.objects.create(first_name="Kid")
    LearningProfile.objects.create(user=learner)
    Guardianship.objects.create(guardian=guardian, learner=learner, role="parent")
    return guardian, learner


def test_wards_requires_auth(client, settings):
    settings.BOT_TOKEN = TOKEN
    assert client.get("/webapp/api/wards/").status_code == 401


def test_wards_lists(client, settings):
    settings.BOT_TOKEN = TOKEN
    _guardian, learner = _guardian_ward()
    r = client.get("/webapp/api/wards/", HTTP_X_TELEGRAM_INIT_DATA=_init_data(700))
    assert [w["id"] for w in r.json()["wards"]] == [learner.id]


def test_ward_settings_guarded(client, settings):
    settings.BOT_TOKEN = TOKEN
    _guardian_ward()
    other = User.objects.create(first_name="Z")
    LearningProfile.objects.create(user=other)
    r = client.get(
        f"/webapp/api/ward/{other.id}/settings/", HTTP_X_TELEGRAM_INIT_DATA=_init_data(700)
    )
    assert r.status_code == 403  # not this guardian's ward


def test_ward_settings_get_and_post(client, settings):
    settings.BOT_TOKEN = TOKEN
    _guardian, learner = _guardian_ward()
    auth = _init_data(700)
    got = client.get(f"/webapp/api/ward/{learner.id}/settings/", HTTP_X_TELEGRAM_INIT_DATA=auth)
    assert got.json()["words_per_session"] == 10
    client.post(
        f"/webapp/api/ward/{learner.id}/settings/",
        data=json.dumps({"words_per_session": 25, "en_voice": "en-US-GuyNeural"}),
        content_type="application/json", HTTP_X_TELEGRAM_INIT_DATA=auth,
    )
    p = LearningProfile.objects.get(user=learner)
    assert p.words_per_session == 25
    assert p.en_voice == "en-US-GuyNeural"
