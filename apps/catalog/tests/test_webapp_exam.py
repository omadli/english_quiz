import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from django.utils import timezone

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, LearningProfile, SessionWord

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


def _session_with_words():
    user = User.objects.create(first_name="Kid")
    TelegramAccount.objects.create(user=user, telegram_id=42)
    LearningProfile.objects.create(user=user)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    words = [Word.objects.create(unit=unit, en=f"w{i}", uz=f"u{i}", order=i) for i in range(1, 7)]
    session = DailySession.objects.create(
        user=user, date=timezone.localdate(), status=DailySession.Status.DELIVERED
    )
    for i, w in enumerate(words, 1):
        SessionWord.objects.create(daily_session=session, word=w, order=i)
    return user, words


def test_exam_requires_auth(client, settings):
    settings.BOT_TOKEN = TOKEN
    assert client.get("/webapp/api/exam/").status_code == 401


def test_exam_returns_sections(client, settings):
    settings.BOT_TOKEN = TOKEN
    _session_with_words()
    r = client.get("/webapp/api/exam/", HTTP_X_TELEGRAM_INIT_DATA=_init(42))
    assert r.status_code == 200
    assert [s["kind"] for s in r.json()["sections"]] == ["quiz", "writing", "listening"]


def test_exam_submit_scores(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user, words = _session_with_words()
    body = {"answers": [
        {"word_id": words[0].id, "kind": "quiz", "answer": words[0].uz},        # correct
        {"word_id": words[1].id, "kind": "writing", "answer": "nope"},          # wrong
    ]}
    r = client.post(
        "/webapp/api/exam/submit/", data=json.dumps(body),
        content_type="application/json", HTTP_X_TELEGRAM_INIT_DATA=_init(42),
    )
    assert r.status_code == 200
    assert r.json() == {"score": 1, "total": 2}
