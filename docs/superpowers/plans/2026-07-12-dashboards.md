# Student Dashboards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A per-student dashboard (learned words, exam accuracy trend, most-errored words, missed-plan days, streak, 30-day activity) — viewable by the learner (Profil) and by their guardian (Nazorat), with inline-SVG charts.

**Architecture:** One pure service `build_dashboard(user, days=30)` computes everything from existing models. Two initData-authed endpoints expose it (self + guarded ward). The Mini App renders `dashboardHTML(d)` with hand-rolled SVG/CSS (no chart lib).

**Tech Stack:** Django 6 ORM aggregates, pytest; vanilla JS + inline SVG.

## Global Constraints

- `ruff check .` passes; line-length 100. Tests `python -m uv run pytest --reuse-db` (Docker db up, one run at a time). TDD; frequent commits. No live bot locally.
- No new model, no migration. Reuse `compute_streak`, `ward_profile`/`_profile_from_request`, `settingsHTML`/`getJSON` patterns.
- `date.weekday()` is Monday=0..Sunday=6 — matches `study_weekdays`.
- `missed_days` must be bounded by first activity date (else pre-signup days count as missed).
- Work on branch `dashboards`; merge to main only when green.

---

### Task 1: `build_dashboard` service

**Files:**
- Create: `apps/learning/services/dashboard.py`
- Test: `apps/learning/tests/test_dashboard.py`

**Interfaces:**
- Produces: `build_dashboard(user, days: int = 30) -> dict` (keys: learned, total, streak, accuracy{correct,answered,pct}, trend[], error_words[], missed_days{count,dates}, activity[]).

- [ ] **Step 1: Write the failing test**

```python
# apps/learning/tests/test_dashboard.py
import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, ExamQuestion, LearnedWord, LearningProfile
from apps.learning.services.dashboard import build_dashboard

pytestmark = pytest.mark.django_db


def _words(n):
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    return [Word.objects.create(unit=unit, en=f"w{i}", uz=f"t{i}", order=i) for i in range(1, n + 1)]


def _session(user, date, status, score=None, total=None):
    return DailySession.objects.create(user=user, date=date, status=status, score=score, total=total)


def test_dashboard_learned_streak_accuracy():
    user = User.objects.create(first_name="Kid")
    LearningProfile.objects.create(user=user, study_weekdays=[0, 1, 2, 3, 4, 5, 6])
    words = _words(5)
    LearnedWord.objects.create(user=user, word=words[0])
    LearnedWord.objects.create(user=user, word=words[1])
    today = timezone.localdate()
    s = _session(user, today, DailySession.Status.COMPLETED, score=2, total=3)
    ExamQuestion.objects.create(daily_session=s, word=words[0], question_type="en_uz",
                                poll_id="p1", correct_option=0, is_correct=True)
    ExamQuestion.objects.create(daily_session=s, word=words[1], question_type="en_uz",
                                poll_id="p2", correct_option=0, is_correct=True)
    ExamQuestion.objects.create(daily_session=s, word=words[2], question_type="en_uz",
                                poll_id="p3", correct_option=0, is_correct=False)
    d = build_dashboard(user)
    assert d["learned"] == 2
    assert d["total"] == 5
    assert d["streak"] == 1
    assert d["accuracy"] == {"correct": 2, "answered": 3, "pct": 67}
    assert d["error_words"][0]["en"] == "w3" and d["error_words"][0]["wrong"] == 1


def test_dashboard_missed_days_respects_studydays_and_first_activity():
    user = User.objects.create(first_name="Kid")
    LearningProfile.objects.create(user=user, study_weekdays=[0, 1, 2, 3, 4, 5, 6])  # every day
    today = timezone.localdate()
    # first activity 3 days ago (completed); yesterday no session -> missed; days before are ignored
    _session(user, today - datetime.timedelta(days=3), DailySession.Status.COMPLETED)
    _session(user, today - datetime.timedelta(days=1), DailySession.Status.DELIVERED)  # not completed
    d = build_dashboard(user)
    dates = d["missed_days"]["dates"]
    assert (today - datetime.timedelta(days=1)).isoformat() in dates      # study day, not completed
    assert (today - datetime.timedelta(days=2)).isoformat() in dates      # between first activity & now
    assert (today - datetime.timedelta(days=5)).isoformat() not in dates  # before first activity


def test_dashboard_rest_day_not_missed():
    user = User.objects.create(first_name="Kid")
    today = timezone.localdate()
    rest = today.weekday()  # make ONLY today's weekday a study day → all others are rest days
    LearningProfile.objects.create(user=user, study_weekdays=[rest])
    _session(user, today - datetime.timedelta(days=7), DailySession.Status.COMPLETED)  # first activity
    d = build_dashboard(user)
    # a day 3 days ago is (almost surely) a rest day → never missed
    assert (today - datetime.timedelta(days=3)).isoformat() not in d["missed_days"]["dates"]


def test_dashboard_empty_user():
    user = User.objects.create(first_name="New")
    LearningProfile.objects.create(user=user)
    d = build_dashboard(user)
    assert d["accuracy"] == {"correct": 0, "answered": 0, "pct": 0}
    assert d["error_words"] == []
    assert d["missed_days"]["count"] == 0
    assert len(d["activity"]) == 30
```

- [ ] **Step 2: Run to verify it fails** — Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# apps/learning/services/dashboard.py
import datetime

from django.db.models import Count, Q
from django.utils import timezone

from apps.catalog.models import Word
from apps.learning.models import DailySession, ExamQuestion, LearnedWord
from apps.relations.services.reports import compute_streak


def build_dashboard(user, days: int = 30) -> dict:
    today = timezone.localdate()
    start = today - datetime.timedelta(days=days - 1)

    answered = ExamQuestion.objects.filter(daily_session__user=user, is_correct__isnull=False)
    correct = answered.filter(is_correct=True).count()
    answered_n = answered.count()
    pct = round(correct / answered_n * 100) if answered_n else 0

    trend = [
        {"date": r["daily_session__date"].isoformat(), "correct": r["correct"], "total": r["n"]}
        for r in answered.filter(daily_session__date__gte=start)
        .values("daily_session__date")
        .annotate(n=Count("id"), correct=Count("id", filter=Q(is_correct=True)))
        .order_by("daily_session__date")
    ]

    error_words = [
        {"en": r["word__en"], "uz": r["word__uz"], "wrong": r["wrong"]}
        for r in ExamQuestion.objects.filter(daily_session__user=user, is_correct=False)
        .values("word__en", "word__uz")
        .annotate(wrong=Count("id"))
        .order_by("-wrong")[:10]
    ]

    sessions = {
        s.date: s
        for s in DailySession.objects.filter(user=user, date__gte=start, date__lte=today)
    }
    first_activity = (
        DailySession.objects.filter(user=user).order_by("date").values_list("date", flat=True).first()
    )
    profile = getattr(user, "learning_profile", None)  # reverse O2O DoesNotExist inherits AttributeError
    study_weekdays = set(profile.study_weekdays) if profile else set()

    activity, missed = [], []
    d = start
    while d <= today:
        s = sessions.get(d)
        activity.append({
            "date": d.isoformat(),
            "status": s.status if s else "none",
            "score": s.score if s else None,
            "total": s.total if s else None,
        })
        completed = s is not None and s.status == DailySession.Status.COMPLETED
        if (
            d < today                              # today isn't "missed" yet
            and d.weekday() in study_weekdays
            and first_activity is not None and d >= first_activity
            and not completed
        ):
            missed.append(d.isoformat())
        d += datetime.timedelta(days=1)

    return {
        "learned": LearnedWord.objects.filter(user=user).count(),
        "total": Word.objects.count(),
        "streak": compute_streak(user),
        "accuracy": {"correct": correct, "answered": answered_n, "pct": pct},
        "trend": trend,
        "error_words": error_words,
        "missed_days": {"count": len(missed), "dates": missed},
        "activity": activity,
    }
```

- [ ] **Step 4: Run tests** — Expected: PASS (4).
- [ ] **Step 5: Commit**

```bash
git add apps/learning/services/dashboard.py apps/learning/tests/test_dashboard.py
git commit -m "feat(learning): build_dashboard service (accuracy, error words, missed days, activity)"
```

---

### Task 2: Web dashboard API

**Files:**
- Modify: `apps/catalog/views.py`, `config/urls.py`
- Test: `apps/catalog/tests/test_webapp_dashboard.py`

**Interfaces:**
- Produces: `api_dashboard(request)`; `api_ward_dashboard(request, learner_id)`. Routes `webapp/api/dashboard/`, `webapp/api/ward/<int:learner_id>/dashboard/`.

- [ ] **Step 1: Write the failing test**

```python
# apps/catalog/tests/test_webapp_dashboard.py
import hashlib, hmac, json, time
from urllib.parse import urlencode

import pytest

from apps.accounts.models import TelegramAccount, User
from apps.learning.models import LearningProfile
from apps.relations.models import Guardianship

TOKEN = "123:TESTTOKEN"
pytestmark = pytest.mark.django_db


def _init(uid):
    f = {"auth_date": str(int(time.time())),
         "user": json.dumps({"id": uid, "first_name": "G"}, separators=(",", ":"))}
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
    assert "accuracy" in r.json() and "activity" in r.json()


def test_ward_dashboard_guarded(client, settings):
    settings.BOT_TOKEN = TOKEN
    guardian = User.objects.create(first_name="Mom")
    TelegramAccount.objects.create(user=guardian, telegram_id=700)
    ward = User.objects.create(first_name="Kid"); LearningProfile.objects.create(user=ward)
    other = User.objects.create(first_name="Z"); LearningProfile.objects.create(user=other)
    Guardianship.objects.create(guardian=guardian, learner=ward, role="parent")
    auth = _init(700)
    assert client.get(f"/webapp/api/ward/{other.id}/dashboard/",
                      HTTP_X_TELEGRAM_INIT_DATA=auth).status_code == 403
    ok = client.get(f"/webapp/api/ward/{ward.id}/dashboard/", HTTP_X_TELEGRAM_INIT_DATA=auth)
    assert ok.status_code == 200 and "streak" in ok.json()
```

- [ ] **Step 2: Run to verify it fails** — Expected: FAIL.

- [ ] **Step 3: Implement — `apps/catalog/views.py`**

Add import: `from apps.learning.services.dashboard import build_dashboard`. Add views (near `api_wards`):

```python
@csrf_exempt
def api_dashboard(request):
    profile = _profile_from_request(request)
    if profile is None:
        return JsonResponse({"error": "unauthorized"}, status=401)
    return JsonResponse(build_dashboard(profile.user))


@csrf_exempt
def api_ward_dashboard(request, learner_id: int):
    caller = _profile_from_request(request)
    if caller is None:
        return JsonResponse({"error": "unauthorized"}, status=401)
    profile = ward_profile(caller.user, learner_id)
    if profile is None:
        return JsonResponse({"error": "forbidden"}, status=403)
    return JsonResponse(build_dashboard(profile.user))
```

- [ ] **Step 4: Routes — `config/urls.py`**

```python
    path("webapp/api/dashboard/", catalog_views.api_dashboard, name="webapp_dashboard"),
    path("webapp/api/ward/<int:learner_id>/dashboard/", catalog_views.api_ward_dashboard,
         name="webapp_ward_dashboard"),
```

- [ ] **Step 5: Run tests** — Expected: PASS (3).
- [ ] **Step 6: Commit**

```bash
git add apps/catalog/views.py config/urls.py apps/catalog/tests/test_webapp_dashboard.py
git commit -m "feat(webapp): dashboard API (self + guarded ward)"
```

---

### Task 3: Mini App dashboard (inline-SVG charts)

**Files:**
- Modify: `templates/webapp/index.html`

**Before writing chart code, read the `dataviz` skill** (chart color/size/consistency).

- [ ] **Step 1: Implement `dashboardHTML(d)` + wiring**

Add helpers near `wordCard`. Stat tiles + an SVG accuracy-trend bar chart + a 30-day activity grid + error-words list + missed-days. Representative code:

```javascript
    function _bar(trend) {
      if (!trend.length) return `<p class="text-xs text-muted">Hali imtihon yo'q.</p>`;
      const w = 300, h = 70, n = trend.length, bw = Math.max(4, Math.floor(w / n) - 2);
      const bars = trend.map((t, i) => {
        const pct = t.total ? t.correct / t.total : 0;
        const bh = Math.round(pct * (h - 8)) + 2;
        const x = i * (w / n);
        const col = pct >= 0.7 ? "#34d399" : pct >= 0.4 ? "#fbbf24" : "#f87171";
        return `<rect x="${x.toFixed(1)}" y="${h - bh}" width="${bw}" height="${bh}" rx="1.5" fill="${col}"/>`;
      }).join("");
      return `<svg viewBox="0 0 ${w} ${h}" class="w-full" preserveAspectRatio="none" role="img" aria-label="Aniqlik trendi">${bars}</svg>`;
    }
    function _grid(activity) {
      const cell = (a) => {
        const c = a.status === "completed" ? "bg-emerald-400"
          : a.status === "none" ? "bg-line" : "bg-amber-400/70";
        return `<div class="aspect-square rounded-sm ${c}" title="${a.date}"></div>`;
      };
      return `<div class="grid grid-cols-10 gap-1">${activity.map(cell).join("")}</div>`;
    }
    function dashboardHTML(d) {
      const tile = (v, l) => `<div class="rounded-2xl bg-card border border-line py-4 text-center"><div class="text-2xl font-bold">${v}</div><div class="text-[11px] text-muted">${l}</div></div>`;
      const errs = d.error_words.length
        ? d.error_words.map((e) => `<div class="flex justify-between text-[13px] py-0.5"><span><b class="text-emerald-400">${esc(e.en)}</b> — ${esc(e.uz)}</span><span class="text-rose-400">${e.wrong}×</span></div>`).join("")
        : `<p class="text-xs text-muted">Xato so'z yo'q 🎉</p>`;
      return `
        <div class="grid grid-cols-3 gap-3">
          ${tile(d.streak + "🔥", "streak")}
          ${tile(d.accuracy.pct + "%", "aniqlik")}
          ${tile(d.learned, "yodlandi")}
        </div>
        <div class="rounded-2xl bg-card border border-line p-4">
          <div class="text-sm font-semibold mb-2">📈 Aniqlik trendi</div>${_bar(d.trend)}</div>
        <div class="rounded-2xl bg-card border border-line p-4">
          <div class="text-sm font-semibold mb-2">🗓 Faollik (30 kun)</div>${_grid(d.activity)}
          <div class="text-[11px] text-muted mt-2">Bajarilmagan kunlar: <b>${d.missed_days.count}</b></div></div>
        <div class="rounded-2xl bg-card border border-line p-4">
          <div class="text-sm font-semibold mb-2">❌ Ko'p xato so'zlar</div>${errs}</div>`;
    }
    async function loadDashboard(boxId, url) {
      const box = document.getElementById(boxId);
      if (!box || !initData) return;
      try { box.innerHTML = dashboardHTML(await getJSON(url)); } catch (e) { /* leave empty */ }
    }
```

Wire self dashboard into `showProfile()` — add `<div id="dash" class="space-y-3"></div>` before `<div id="settings">` and call `loadDashboard("dash", "api/dashboard/")`.

Wire ward dashboard: in `ward_menu_keyboard`… (bot) — no. In the SPA `showWardSettings` sibling, add a 📊 button. Simplest: in `loadWards()`'s per-ward button row, render TWO buttons (⚙️ settings, 📊 dashboard). Update the ward button markup to:

```javascript
        wards.map((w) => `<div class="flex gap-2"><button data-id="${w.id}" data-name="${esc(w.name)}" class="js-ward flex-1 text-left rounded-xl bg-line/40 px-3 py-2 text-sm">${esc(w.name)} ⚙️</button><button data-id="${w.id}" data-name="${esc(w.name)}" class="js-warddash rounded-xl bg-line/40 px-3 py-2 text-sm">📊</button></div>`).join("")
```

and bind `.js-warddash` → `showWardDashboard(id, name)`:

```javascript
    async function showWardDashboard(id, name) {
      setHeader(name, "Dashboard"); setBack(() => showProfile());
      setContent("px-4 py-4 pb-24 space-y-3", `<div id="warddash" class="space-y-3"></div>`);
      loadDashboard("warddash", `ward/${id}/dashboard/`);
    }
```

- [ ] **Step 2: Verify — JS syntax + serves**

```bash
# extract the main <script> and node --check it (see ①'s Task 7 pattern)
```
Full visual check happens live after deploy.

- [ ] **Step 3: Commit**

```bash
git add templates/webapp/index.html
git commit -m "feat(webapp): student dashboard (Profil) + ward dashboard (Nazorat), inline SVG"
```

---

### Task 4: Integration + deploy

- [ ] **Step 1:** `python -m uv run pytest --reuse-db && python -m uv run ruff check .` — all green.
- [ ] **Step 2:** Merge + deploy:

```bash
git checkout main && git merge --no-ff dashboards && git push origin main
```
Watch CI. No migration, no `.env` change.

- [ ] **Step 3: Live verify**

- `https://english.omadli.uz/webapp/api/dashboard/` → 401 (no auth).
- Mini App Profil shows the stats/charts; Nazorat → 📊 shows a ward's dashboard.

---

## Notes

- ③ is the last sub-project. After it, the daily-words + guardian + dashboards program the user asked for on 2026-07-12 is complete.
- Charts are hand-rolled SVG to keep the Mini App self-contained (no CDN).
