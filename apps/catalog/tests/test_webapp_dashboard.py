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


def _init(uid):
    f = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"id": uid, "first_name": "G"}, separators=(",", ":")),
    }
    dcs = "\n".join(f"{k}={f[k]}" for k in sorted(f))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    f["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode(f)


def test_dashboard_requires_auth(client, settings):
    settings.BOT_TOKEN = TOKEN
    assert client.get("/webapp/api/dashboard/").status_code == 401


def test_dashboard_self(client, settings):
    settings.BOT_TOKEN = TOKEN
    u = User.objects.create(first_name="Kid")
    TelegramAccount.objects.create(user=u, telegram_id=500)
    LearningProfile.objects.create(user=u)
    r = client.get("/webapp/api/dashboard/", HTTP_X_TELEGRAM_INIT_DATA=_init(500))
    assert r.status_code == 200
    body = r.json()
    assert "accuracy" in body and "activity" in body and "missed_days" in body


def test_ward_dashboard_guarded(client, settings):
    settings.BOT_TOKEN = TOKEN
    guardian = User.objects.create(first_name="Mom")
    TelegramAccount.objects.create(user=guardian, telegram_id=700)
    ward = User.objects.create(first_name="Kid")
    LearningProfile.objects.create(user=ward)
    other = User.objects.create(first_name="Z")
    LearningProfile.objects.create(user=other)
    Guardianship.objects.create(guardian=guardian, learner=ward, role="parent")
    auth = _init(700)
    assert client.get(
        f"/webapp/api/ward/{other.id}/dashboard/", HTTP_X_TELEGRAM_INIT_DATA=auth
    ).status_code == 403
    ok = client.get(f"/webapp/api/ward/{ward.id}/dashboard/", HTTP_X_TELEGRAM_INIT_DATA=auth)
    assert ok.status_code == 200
    assert "streak" in ok.json()
