import datetime
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
        "signature": "abc123",  # real clients send it; Telegram folds it into the hash
    }
    dcs = "\n".join(f"{k}={f[k]}" for k in sorted(f))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    f["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode(f)


def _make(date, status=DailySession.Status.DELIVERED):
    """A session on `date` with 6 session words, for tg user 42."""
    user = User.objects.filter(telegram__telegram_id=42).first()
    if user is None:
        user = User.objects.create(first_name="Kid")
        TelegramAccount.objects.create(user=user, telegram_id=42)
        LearningProfile.objects.create(user=user)
    book, _ = Book.objects.get_or_create(number=1, defaults={"title": "B1", "slug": "b1"})
    unit, _ = Unit.objects.get_or_create(book=book, number=1)
    words = [
        Word.objects.get_or_create(unit=unit, en=f"w{i}", defaults={"uz": f"u{i}", "order": i})[0]
        for i in range(1, 7)
    ]
    session = DailySession.objects.create(user=user, date=date, status=status)
    for i, w in enumerate(words, 1):
        SessionWord.objects.create(daily_session=session, word=w, order=i)
    return user, session, words


def test_exam_requires_auth(client, settings):
    settings.BOT_TOKEN = TOKEN
    assert client.get("/webapp/api/exam/").status_code == 401


def test_exam_returns_today_exam(client, settings):
    settings.BOT_TOKEN = TOKEN
    _make(timezone.localdate())
    r = client.get("/webapp/api/exam/", HTTP_X_TELEGRAM_INIT_DATA=_init(42))
    assert r.status_code == 200
    exams = r.json()["exams"]
    assert len(exams) == 1 and exams[0]["kind"] == "today"
    assert [s["kind"] for s in exams[0]["sections"]] == ["quiz", "writing", "listening"]


def test_exam_includes_yesterday_makeup(client, settings):
    settings.BOT_TOKEN = TOKEN
    today = timezone.localdate()
    _make(today - datetime.timedelta(days=1))  # unfinished yesterday
    _make(today)  # and a fresh today
    r = client.get("/webapp/api/exam/", HTTP_X_TELEGRAM_INIT_DATA=_init(42))
    kinds = [e["kind"] for e in r.json()["exams"]]
    assert kinds == ["today", "makeup"]


def test_exam_omits_completed_yesterday(client, settings):
    settings.BOT_TOKEN = TOKEN
    today = timezone.localdate()
    _make(today - datetime.timedelta(days=1), status=DailySession.Status.COMPLETED)
    r = client.get("/webapp/api/exam/", HTTP_X_TELEGRAM_INIT_DATA=_init(42))
    assert r.json()["exams"] == []  # nothing due today, yesterday already done


def test_exam_submit_scores_by_session_id(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user, session, words = _make(timezone.localdate())
    body = {"session_id": session.id, "answers": [
        {"word_id": words[0].id, "kind": "quiz", "answer": words[0].uz},   # correct
        {"word_id": words[1].id, "kind": "writing", "answer": "nope"},     # wrong
    ]}
    r = client.post(
        "/webapp/api/exam/submit/", data=json.dumps(body),
        content_type="application/json", HTTP_X_TELEGRAM_INIT_DATA=_init(42),
    )
    assert r.status_code == 200
    assert r.json() == {"score": 1, "total": 2}
    session.refresh_from_db()
    assert session.status == DailySession.Status.COMPLETED


def test_submit_makeup_completes_yesterday(client, settings):
    settings.BOT_TOKEN = TOKEN
    yesterday = timezone.localdate() - datetime.timedelta(days=1)
    _user, session, words = _make(yesterday)
    body = {"session_id": session.id, "answers": [
        {"word_id": words[0].id, "kind": "quiz", "answer": words[0].uz},
    ]}
    r = client.post(
        "/webapp/api/exam/submit/", data=json.dumps(body),
        content_type="application/json", HTTP_X_TELEGRAM_INIT_DATA=_init(42),
    )
    assert r.status_code == 200
    session.refresh_from_db()
    assert session.status == DailySession.Status.COMPLETED  # the missed day heals


def test_submit_rejects_foreign_session(client, settings):
    settings.BOT_TOKEN = TOKEN
    _make(timezone.localdate())  # user 42
    # another user's session
    other = User.objects.create(first_name="Other")
    TelegramAccount.objects.create(user=other, telegram_id=99)
    LearningProfile.objects.create(user=other)
    theirs = DailySession.objects.create(
        user=other, date=timezone.localdate(), status=DailySession.Status.DELIVERED
    )
    body = {"session_id": theirs.id, "answers": []}
    r = client.post(
        "/webapp/api/exam/submit/", data=json.dumps(body),
        content_type="application/json", HTTP_X_TELEGRAM_INIT_DATA=_init(42),
    )
    assert r.status_code == 400  # can't submit someone else's session


def test_submit_rejects_two_day_old_session(client, settings):
    settings.BOT_TOKEN = TOKEN
    old = timezone.localdate() - datetime.timedelta(days=2)
    _user, session, words = _make(old)
    body = {"session_id": session.id, "answers": [
        {"word_id": words[0].id, "kind": "quiz", "answer": words[0].uz},
    ]}
    r = client.post(
        "/webapp/api/exam/submit/", data=json.dumps(body),
        content_type="application/json", HTTP_X_TELEGRAM_INIT_DATA=_init(42),
    )
    assert r.status_code == 400  # retry window is one day only
