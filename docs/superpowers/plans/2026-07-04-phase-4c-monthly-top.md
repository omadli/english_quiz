# Faza 4c — Oylik Top Leaderboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/top` command showing the current month's learner leaderboard (top 10 + the caller's own rank), ranked by correct-answer points from completed exams — no new models.

**Architecture:** A `ranking.py` service aggregates `DailySession` (COMPLETED, this month) by user (`Sum(score)`, `Count`) ordered by points then session-count. A new `/top` handler formats the top-10 + the caller's rank and is wired as an 8th router (factory + test conftest detach list).

**Tech Stack:** Django 6 ORM aggregation (sync) · aiogram 3.x (command) · sync_to_async · pytest + pytest-django + pytest-asyncio.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-04-phase-4c-monthly-top-design.md`. Phases 0-4b complete on `main`.
- Run via uv (not on PATH): `python -m uv run pytest`, `python -m uv run python manage.py ...`. Postgres + Redis via `docker compose up -d db redis`.
- No new models. Metric = `Sum(DailySession.score)` over `status=COMPLETED`, `date__year`/`date__month` = target month, `score__isnull=False`; order `-points, -sessions, user` (last for determinism). Tiebreak = session count.
- `build_monthly_leaderboard(year, month, limit=10)` returns `[{rank, user_id, name, points, sessions}]` (`name` = `first_name or "Anonim"`, `rank` 1-based). `user_month_rank(user, year, month)` returns `(rank, points)` over the FULL ordering (no limit) or `None` if the user has no completed session that month.
- Async handlers reach the ORM ONLY via `sync_to_async`. Text is HTML.
- The `/top` router is the 8th — it MUST be added to BOTH `bot/factory.py` (import + `include_router`) AND `bot/tests/conftest.py`'s `_detach_handler_routers` module list (aiogram singleton routers; without it the 2nd `build_dispatcher()` in the suite raises `RuntimeError`).
- Month boundary uses `timezone.localtime()` (TIME_ZONE = Asia/Tashkent) `.year`/`.month`, matching `DailySession.date` (learner local date).
- OUT of scope (Phase 4d): friend duels. Also deferred: end-of-month broadcast, fairness normalization, privacy opt-out.
- TDD; pristine output. Commit footer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

### Prerequisite (once, before Task 1)

```bash
git checkout main && git checkout -b phase-4c-monthly-top
```

---

### Task 1: Ranking service

**Files:**
- Create: `apps/learning/services/ranking.py`
- Create: `apps/learning/tests/test_ranking.py`

**Interfaces:**
- Consumes: `DailySession` (status COMPLETED, score, date, user).
- Produces:
  - `apps.learning.services.ranking.build_monthly_leaderboard(year, month, limit=10) -> list[dict]`
  - `apps.learning.services.ranking.user_month_rank(user, year, month) -> tuple[int, int] | None`

- [ ] **Step 1: Write the failing tests**

`apps/learning/tests/test_ranking.py`:
```python
import datetime

import pytest

from apps.accounts.models import User
from apps.learning.models import DailySession
from apps.learning.services.ranking import build_monthly_leaderboard, user_month_rank

pytestmark = pytest.mark.django_db


def _completed(user, day, score):
    DailySession.objects.create(
        user=user, date=day, status=DailySession.Status.COMPLETED, score=score, total=10
    )


def test_leaderboard_orders_by_points_then_sessions():
    jul = datetime.date(2026, 7, 1)
    alice = User.objects.create(first_name="Alice")
    bob = User.objects.create(first_name="Bob")
    carol = User.objects.create(first_name="Carol")
    # Alice: 8 (one session). Bob: 8 across two sessions -> ties points, more sessions => ahead.
    _completed(alice, datetime.date(2026, 7, 2), 8)
    _completed(bob, datetime.date(2026, 7, 2), 5)
    _completed(bob, datetime.date(2026, 7, 3), 3)
    _completed(carol, datetime.date(2026, 7, 2), 10)
    board = build_monthly_leaderboard(2026, 7, limit=10)
    names = [e["name"] for e in board]
    assert names == ["Carol", "Bob", "Alice"]  # 10 ; 8/2sess ; 8/1sess
    assert board[0]["rank"] == 1
    assert board[1]["points"] == 8
    assert board[1]["sessions"] == 2


def test_leaderboard_excludes_other_months_and_incomplete():
    alice = User.objects.create(first_name="Alice")
    _completed(alice, datetime.date(2026, 7, 5), 7)
    _completed(alice, datetime.date(2026, 6, 5), 9)  # other month
    DailySession.objects.create(  # incomplete this month
        user=alice, date=datetime.date(2026, 7, 6), status=DailySession.Status.DELIVERED
    )
    board = build_monthly_leaderboard(2026, 7)
    assert len(board) == 1
    assert board[0]["points"] == 7  # only the July completed one


def test_leaderboard_limit():
    for i in range(5):
        u = User.objects.create(first_name=f"U{i}")
        _completed(u, datetime.date(2026, 7, 2), i + 1)
    assert len(build_monthly_leaderboard(2026, 7, limit=3)) == 3


def test_user_month_rank():
    users = []
    for i in range(12):
        u = User.objects.create(first_name=f"U{i}")
        _completed(u, datetime.date(2026, 7, 2), 100 - i)  # U0 highest ... U11 lowest
        users.append(u)
    # U0 rank 1, U11 rank 12 (beyond a top-10 view)
    assert user_month_rank(users[0], 2026, 7) == (1, 100)
    assert user_month_rank(users[11], 2026, 7)[0] == 12
    # a non-participant
    outsider = User.objects.create(first_name="Out")
    assert user_month_rank(outsider, 2026, 7) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest apps/learning/tests/test_ranking.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `apps/learning/services/ranking.py`**

```python
from django.db.models import Count, Sum

from apps.learning.models import DailySession


def _monthly_rows(year: int, month: int) -> list[dict]:
    return list(
        DailySession.objects.filter(
            status=DailySession.Status.COMPLETED,
            date__year=year,
            date__month=month,
            score__isnull=False,
        )
        .values("user", "user__first_name")
        .annotate(points=Sum("score"), sessions=Count("id"))
        .order_by("-points", "-sessions", "user")
    )


def build_monthly_leaderboard(year: int, month: int, limit: int = 10) -> list[dict]:
    return [
        {
            "rank": i + 1,
            "user_id": row["user"],
            "name": row["user__first_name"] or "Anonim",
            "points": row["points"] or 0,
            "sessions": row["sessions"],
        }
        for i, row in enumerate(_monthly_rows(year, month)[:limit])
    ]


def user_month_rank(user, year: int, month: int) -> tuple[int, int] | None:
    for i, row in enumerate(_monthly_rows(year, month)):
        if row["user"] == user.id:
            return (i + 1, row["points"] or 0)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest apps/learning/tests/test_ranking.py -v`
Expected: all PASS.

- [ ] **Step 5: Full suite + ruff + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add apps/learning/services/ranking.py apps/learning/tests/test_ranking.py
git commit -m "feat(learning): monthly leaderboard + user rank service"
```
Expected: full suite passes (190 prior + 4 new = 194); ruff clean.

---

### Task 2: `/top` handler + router

**Files:**
- Create: `bot/handlers/leaderboard.py`
- Modify: `bot/strings.py`
- Create: `bot/tests/test_handlers_leaderboard.py`

**Interfaces:**
- Consumes: `build_monthly_leaderboard`/`user_month_rank` (Task 1).
- Produces: `bot.handlers.leaderboard.router` with `/top`; `bot.handlers.leaderboard.cmd_top`, `_format_leaderboard(entries, own_rank)`.

- [ ] **Step 1: Write the failing tests**

`bot/tests/test_handlers_leaderboard.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import leaderboard

pytestmark = pytest.mark.asyncio


def _entry(rank, name, points, sessions):
    return {"rank": rank, "user_id": rank, "name": name, "points": points, "sessions": sessions}


def test_format_leaderboard_lists_entries():
    text = leaderboard._format_leaderboard(
        [_entry(1, "Alice", 10, 3), _entry(2, "Bob", 8, 2)], None
    )
    assert "Alice" in text
    assert "Bob" in text
    assert "🥇" in text


def test_format_leaderboard_appends_own_rank_when_outside_top():
    text = leaderboard._format_leaderboard([_entry(1, "Alice", 10, 3)], (15, 4))
    assert "15" in text  # own rank shown because 15 > len(entries)=1


def test_format_leaderboard_empty():
    assert leaderboard._format_leaderboard([], None) == leaderboard.strings.TOP_EMPTY


@patch("bot.handlers.leaderboard.user_month_rank", return_value=None)
@patch("bot.handlers.leaderboard.build_monthly_leaderboard")
async def test_cmd_top_sends_board(mock_board, mock_rank):
    mock_board.return_value = [_entry(1, "Alice", 10, 3)]
    message = AsyncMock()
    await leaderboard.cmd_top(message, user=MagicMock())
    message.answer.assert_awaited()
    sent = message.answer.call_args.args[0]
    assert "Alice" in sent
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_handlers_leaderboard.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Add strings**

In `bot/strings.py`, add:
```python
TOP_TITLE = "🏆 <b>Oylik reyting</b>"
TOP_EMPTY = "Bu oyda hali natija yo'q. Imtihonlarni yakunlang! 💪"
TOP_YOUR_RANK = "Sizning o'rningiz: <b>{rank}</b> ({points} ball)"
```

- [ ] **Step 4: Implement `bot/handlers/leaderboard.py`**

```python
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.utils import timezone

from apps.accounts.models import User
from apps.learning.services.ranking import build_monthly_leaderboard, user_month_rank
from bot import strings

router = Router()

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _format_leaderboard(entries: list[dict], own_rank: tuple[int, int] | None) -> str:
    if not entries:
        return strings.TOP_EMPTY
    lines = [strings.TOP_TITLE]
    for e in entries:
        badge = _MEDALS.get(e["rank"], f"{e['rank']}.")
        lines.append(f"{badge} {e['name']} — {e['points']} ball ({e['sessions']} kun)")
    if own_rank is not None and own_rank[0] > len(entries):
        lines.append("")
        lines.append(strings.TOP_YOUR_RANK.format(rank=own_rank[0], points=own_rank[1]))
    return "\n".join(lines)


@router.message(Command("top"))
async def cmd_top(message: Message, user: User) -> None:
    now = timezone.localtime()
    entries = await sync_to_async(build_monthly_leaderboard)(now.year, now.month, 10)
    own = await sync_to_async(user_month_rank)(user, now.year, now.month)
    await message.answer(_format_leaderboard(entries, own))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m uv run pytest bot/tests/test_handlers_leaderboard.py -v`
Expected: all PASS.

- [ ] **Step 6: Full suite + ruff + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/handlers/leaderboard.py bot/strings.py bot/tests/test_handlers_leaderboard.py
git commit -m "feat(bot): /top monthly leaderboard command"
```

---

### Task 3: Wire router + conftest + docs + gate

**Files:**
- Modify: `bot/factory.py`, `bot/tests/conftest.py`, `Readme.md`
- Create: `bot/tests/test_factory_leaderboard.py`

**Interfaces:**
- Produces: `leaderboard.router` included in `build_dispatcher` (8th router); documented usage.

- [ ] **Step 1: Write the failing test**

`bot/tests/test_factory_leaderboard.py`:
```python
def test_dispatcher_includes_leaderboard_router(settings):
    settings.REDIS_URL = "redis://localhost:6379/1"
    from bot.factory import build_dispatcher

    dp = build_dispatcher()
    assert len(dp.sub_routers) >= 8  # + leaderboard
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m uv run pytest bot/tests/test_factory_leaderboard.py -v`
Expected: FAIL — only 7 routers wired.

- [ ] **Step 3: Wire the router in `bot/factory.py`**

Add `leaderboard` to the handlers import (keep alphabetical):
```python
from bot.handlers import (
    common,
    group_quiz,
    leaderboard,
    onboarding,
    quiz,
    relations,
    settings,
    start,
)
```
and, in `build_dispatcher`, after `dp.include_router(relations.router)`:
```python
    dp.include_router(leaderboard.router)
```
(If the current import is a single line, just add `leaderboard` in alphabetical position and keep it valid.)

- [ ] **Step 4: Update `bot/tests/conftest.py`**

In `_detach_handler_routers`, add `leaderboard` to BOTH the `from bot.handlers import ...` line AND the module list/tuple the loop iterates (alphabetical, next to the other 7). Read the file first to match its exact style.

- [ ] **Step 5: Run the factory tests**

Run: `python -m uv run pytest bot/tests/test_factory_leaderboard.py bot/tests/test_factory.py bot/tests/test_factory_group_quiz.py bot/tests/test_factory_relations.py -v`
Expected: PASS (≥8, and the existing ≥4/≥6/≥7 checks still hold).

- [ ] **Step 6: Update `Readme.md`**

Add a "Monthly leaderboard" subsection under the Bot section:
```markdown
## Monthly leaderboard

Learners send `/top` to see the current month's leaderboard — the top 10 by
correct-answer points from completed exams (ties broken by number of study
days), plus their own rank if they're outside the top 10.
```

- [ ] **Step 7: Full gate + commit**

```bash
python -m uv run pytest
python -m uv run ruff check .
git add bot/factory.py bot/tests/conftest.py Readme.md bot/tests/test_factory_leaderboard.py
git commit -m "feat(bot): wire leaderboard router into dispatcher + docs"
```
Expected: full suite passes; ruff clean whole-repo.

---

## Self-Review (completed by plan author)

**Spec coverage** — every Phase 4c spec section maps to a task:
- §4 services (build_monthly_leaderboard, user_month_rank) → Task 1
- §5 handler (/top, router) → Task 2
- §5 wiring (factory + conftest) → Task 3
- §6 tests → each task ships tests; sender mocked
- §8 DoD → Task 3 gate

**Placeholder scan** — no TBD/TODO. The 8th-router conftest update (the one cross-cutting gotcha) is explicit in Task 3 Step 4.

**Type/name consistency** — `build_monthly_leaderboard`/`user_month_rank` (Task 1) consumed with matching names + patch sites (`bot.handlers.leaderboard.*`) in Task 2. Entry dict keys (`rank`/`name`/`points`/`sessions`) match between service and `_format_leaderboard`. `_monthly_rows` shared by both service functions. `timezone.localtime().year/.month` matches the `date__year`/`date__month` filter.

**Ordering note** — `docker compose up -d db redis` for the DB tests (Task 1) and the factory test (Task 3, needs Redis for RedisStorage). Task 3 adds the 8th router; the conftest detach-list update is REQUIRED or the full suite's second `build_dispatcher()` raises `RuntimeError`.
