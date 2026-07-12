# Guardian Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a parent/teacher manage each ward's daily settings (words/day, weekdays, morning/exam time, audio, EN/UZ voice, repeat, nudges) + report + revoke — from BOTH the bot and the Mini App — guarded by active guardianship.

**Architecture:** A shared guard service (`active_guardianship`/`ward_profile`/`revoke`) backs both surfaces. Bot: `/wards` → per-ward inline pickers (reuse preset keyboards, callbacks carry the learner_id, no FSM). Web: initData-authed `api_wards`/`api_ward_settings` + a "Nazorat" section in the Mini App Profil tab reusing the existing settings form.

**Tech Stack:** Django 6, aiogram 3.x, pytest.

## Global Constraints

- `ruff check .` passes; line-length 100.
- Tests: `python -m uv run pytest --reuse-db` (Docker Postgres up). One pytest process at a time.
- TDD; frequent commits. Do NOT run a live bot locally (prod webhook).
- Every ward read/write goes through `active_guardianship` — no unguarded access.
- New bot router MUST be added to `bot/factory.py` AND the detach tuple in `bot/tests/conftest.py`.
- Reuse: `guardian_wards` (relations/reports.py), `_clean_settings`/`_profile_payload`/`_profile_from_request` (catalog/views.py), preset keyboards (`WORDS_PRESETS`/`MORNING_PRESETS`/`EXAM_PRESETS`), `EN_VOICES`/`UZ_VOICES`, `settingsHTML` (SPA).
- Callback `wsv:<lid>:<field>:<value>` — value must contain no `:` (words/repeat int, voice id colon-free, time as preset INDEX). Parse `split(":", 3)`.

---

### Task 1: Guardian guard service

**Files:**
- Create: `apps/relations/services/guardian.py`
- Test: `apps/relations/tests/test_guardian_service.py`

**Interfaces:**
- Produces: `active_guardianship(guardian, learner_id) -> Guardianship | None`; `ward_profile(guardian, learner_id) -> LearningProfile | None`; `revoke(guardian, learner_id) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# apps/relations/tests/test_guardian_service.py
import pytest

from apps.accounts.models import User
from apps.learning.models import LearningProfile
from apps.relations.models import Guardianship
from apps.relations.services import guardian as g

pytestmark = pytest.mark.django_db


def _pair():
    guardian = User.objects.create(first_name="Mom")
    learner = User.objects.create(first_name="Kid")
    return guardian, learner


def test_active_guardianship_only_when_active():
    guardian, learner = _pair()
    link = Guardianship.objects.create(guardian=guardian, learner=learner, role="parent")
    assert g.active_guardianship(guardian, learner.id) == link
    link.status = Guardianship.Status.REVOKED
    link.save()
    assert g.active_guardianship(guardian, learner.id) is None


def test_ward_profile_guarded():
    guardian, learner = _pair()
    assert g.ward_profile(guardian, learner.id) is None  # not linked
    Guardianship.objects.create(guardian=guardian, learner=learner, role="parent")
    prof = g.ward_profile(guardian, learner.id)
    assert isinstance(prof, LearningProfile)
    assert prof.user_id == learner.id


def test_revoke():
    guardian, learner = _pair()
    Guardianship.objects.create(guardian=guardian, learner=learner, role="teacher")
    assert g.revoke(guardian, learner.id) is True
    assert g.active_guardianship(guardian, learner.id) is None
    assert g.revoke(guardian, learner.id) is False  # already revoked
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m uv run pytest apps/relations/tests/test_guardian_service.py -v --reuse-db`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# apps/relations/services/guardian.py
from apps.learning.models import LearningProfile
from apps.relations.models import Guardianship


def active_guardianship(guardian, learner_id) -> Guardianship | None:
    return Guardianship.objects.filter(
        guardian=guardian, learner_id=learner_id, status=Guardianship.Status.ACTIVE
    ).first()


def ward_profile(guardian, learner_id) -> LearningProfile | None:
    if active_guardianship(guardian, learner_id) is None:
        return None
    profile, _ = LearningProfile.objects.get_or_create(user_id=learner_id)
    return profile


def revoke(guardian, learner_id) -> bool:
    link = active_guardianship(guardian, learner_id)
    if link is None:
        return False
    link.status = Guardianship.Status.REVOKED
    link.save(update_fields=["status", "updated_at"])
    return True
```

- [ ] **Step 4: Run tests** — Expected: PASS (3).
- [ ] **Step 5: Commit**

```bash
git add apps/relations/services/guardian.py apps/relations/tests/test_guardian_service.py
git commit -m "feat(relations): guardian guard service (active/ward_profile/revoke)"
```

---

### Task 2: Notify guardian on attach

**Files:**
- Modify: `bot/handlers/start.py`, `bot/strings.py`
- Test: `bot/tests/test_handlers_start.py` (append)

**Interfaces:**
- Produces: `start._guardian_notify_info(guardianship) -> tuple[int, str] | None` (telegram_id, role label).

- [ ] **Step 1: Write the failing test**

```python
# bot/tests/test_handlers_start.py  (append)
import pytest
from apps.accounts.models import TelegramAccount, User
from apps.relations.models import Guardianship
from bot.handlers import start as start_mod


@pytest.mark.django_db
def test_guardian_notify_info_returns_tg_and_role():
    guardian = User.objects.create(first_name="Mom")
    TelegramAccount.objects.create(user=guardian, telegram_id=8001)
    learner = User.objects.create(first_name="Kid")
    link = Guardianship.objects.create(guardian=guardian, learner=learner, role="parent")
    tg_id, role = start_mod._guardian_notify_info(link)
    assert tg_id == 8001
    assert "ota" in role.lower()


@pytest.mark.django_db
def test_guardian_notify_info_none_without_telegram():
    guardian = User.objects.create(first_name="Mom")  # no TelegramAccount
    learner = User.objects.create(first_name="Kid")
    link = Guardianship.objects.create(guardian=guardian, learner=learner, role="teacher")
    assert start_mod._guardian_notify_info(link) is None
```

- [ ] **Step 2: Run to verify it fails** — Expected: FAIL (`_guardian_notify_info` missing).

- [ ] **Step 3: Add string** — `bot/strings.py`:

```python
WARD_JOINED = "👤 <b>{name}</b> siz bilan ({role}) ulandi. /wards orqali sozlang."
```

- [ ] **Step 4: Implement — `bot/handlers/start.py`**

Add imports: `from apps.relations.models import Guardianship`. Add helpers + call after successful redeem:

```python
def _guardian_notify_info(guardianship) -> tuple[int, str] | None:
    account = getattr(guardianship.guardian, "telegram", None)
    if account is None:
        return None
    role = "ota-ona" if guardianship.role == Guardianship.Role.PARENT else "o'qituvchi"
    return account.telegram_id, role


async def _notify_guardian(bot, guardianship, learner) -> None:
    info = await sync_to_async(_guardian_notify_info)(guardianship)
    if info is None:
        return
    tg_id, role = info
    try:
        await bot.send_message(
            tg_id, strings.WARD_JOINED.format(name=learner.full_name or learner.pk, role=role)
        )
    except Exception:  # best-effort; guardian may have blocked the bot
        pass
```

In `cmd_start`, extend the redeem branch:

```python
    if payload.startswith("g"):
        guardianship = await sync_to_async(redeem_token)(payload[1:], user)
        if guardianship is not None:
            await message.answer(strings.LINKED_OK)
            await _notify_guardian(message.bot, guardianship, user)
```

- [ ] **Step 5: Run tests** — Expected: PASS.
- [ ] **Step 6: Commit**

```bash
git add bot/handlers/start.py bot/strings.py bot/tests/test_handlers_start.py
git commit -m "feat(bot): notify guardian when a ward attaches"
```

---

### Task 3: Bot /wards list + ward menu + revoke

**Files:**
- Create: `bot/keyboards/guardian.py`, `bot/handlers/guardian.py`
- Modify: `bot/factory.py`, `bot/tests/conftest.py`, `bot/strings.py`
- Test: `bot/tests/test_handlers_guardian.py`

**Interfaces:**
- Consumes: `guardian_wards`, `active_guardianship`, `revoke`, `build_learner_report`.
- Produces: `guardian.router`; keyboards `wards_manage_keyboard(wards)` (`ward:<lid>`), `ward_menu_keyboard(lid)`.

- [ ] **Step 1: Write the failing test**

```python
# bot/tests/test_handlers_guardian.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.accounts.models import TelegramAccount, User
from apps.relations.models import Guardianship
from bot.handlers import guardian as gh

pytestmark = pytest.mark.django_db


def _guardian_with_ward():
    guardian = User.objects.create(first_name="Mom")
    TelegramAccount.objects.create(user=guardian, telegram_id=9001)
    learner = User.objects.create(first_name="Kid")
    Guardianship.objects.create(guardian=guardian, learner=learner, role="parent")
    return guardian, learner


@pytest.mark.asyncio
async def test_cmd_wards_lists(monkeypatch):
    guardian, learner = _guardian_with_ward()
    message = AsyncMock()
    await gh.cmd_wards(message, user=guardian)
    message.answer.assert_awaited()


@pytest.mark.asyncio
async def test_wset_rejects_non_guardian():
    outsider = User.objects.create(first_name="X")
    learner = User.objects.create(first_name="Kid")
    callback = AsyncMock()
    callback.data = f"wset:{learner.id}"
    await gh.open_ward_settings(callback, user=outsider)
    callback.message.edit_text.assert_not_awaited()  # guard blocks


@pytest.mark.asyncio
async def test_wrevoke_sets_revoked():
    guardian, learner = _guardian_with_ward()
    callback = AsyncMock()
    callback.data = f"wrevoke:{learner.id}"
    await gh.do_revoke(callback, user=guardian)
    assert Guardianship.objects.get(guardian=guardian, learner=learner).status == \
        Guardianship.Status.REVOKED
```

- [ ] **Step 2: Run to verify it fails** — Expected: FAIL (module missing).

- [ ] **Step 3: Add strings — `bot/strings.py`**

```python
WARDS_PICK = "👨‍👩‍👧 O'quvchini tanlang:"
WARD_MENU = "👤 <b>{name}</b> — nima qilamiz?"
WARD_REVOKED = "🗑 O'quvchi ajratildi."
```

- [ ] **Step 4: Implement keyboards — `bot/keyboards/guardian.py`**

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import strings


def wards_manage_keyboard(wards) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=w.full_name or str(w.pk), callback_data=f"ward:{w.pk}")]
        for w in wards
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ward_menu_keyboard(lid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data=f"wset:{lid}")],
        [InlineKeyboardButton(text="📊 Hisobot", callback_data=f"rep:{lid}")],
        [InlineKeyboardButton(text="🗑 Ajratish", callback_data=f"wrevoke:{lid}")],
    ])
```

- [ ] **Step 5: Implement handlers — `bot/handlers/guardian.py`**

```python
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async

from apps.accounts.models import User
from apps.relations.services.guardian import active_guardianship, revoke
from apps.relations.services.reports import guardian_wards
from bot import strings
from bot.keyboards.guardian import ward_menu_keyboard, wards_manage_keyboard

router = Router()


@router.message(Command("wards"))
async def cmd_wards(message: Message, user: User) -> None:
    wards = await sync_to_async(guardian_wards)(user)
    if not wards:
        await message.answer(strings.NO_WARDS)
        return
    await message.answer(strings.WARDS_PICK, reply_markup=wards_manage_keyboard(wards))


@router.callback_query(F.data.startswith("ward:"))
async def open_ward(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    lid = int(callback.data.split(":")[1])
    link = await sync_to_async(active_guardianship)(user, lid)
    if link is None:
        return
    name = await sync_to_async(lambda: (link.learner.full_name or link.learner_id))()
    await callback.message.edit_text(
        strings.WARD_MENU.format(name=name), reply_markup=ward_menu_keyboard(lid)
    )


@router.callback_query(F.data.startswith("wrevoke:"))
async def do_revoke(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    lid = int(callback.data.split(":")[1])
    if await sync_to_async(revoke)(user, lid):
        await callback.message.edit_text(strings.WARD_REVOKED)
```

(`open_ward_settings`/`wset:` handler is added in Task 4. For this task's `test_wset_rejects_non_guardian` to import, add a stub now that guards and returns — Task 4 fills it. Minimal stub:)

```python
@router.callback_query(F.data.startswith("wset:"))
async def open_ward_settings(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    lid = int(callback.data.split(":")[1])
    profile = await sync_to_async(_ward_profile)(user, lid)
    if profile is None:
        return
    # Task 4 renders the settings keyboard here.
```

with helper `from apps.relations.services.guardian import ward_profile as _ward_profile` (import alias) — or import `ward_profile` and call it.

- [ ] **Step 6: Wire router — `bot/factory.py`** (add `guardian` to the import tuple and `dp.include_router(guardian.router)`) AND **`bot/tests/conftest.py`** (add `guardian` to BOTH the import list and the detach tuple).

- [ ] **Step 7: Run tests**

Run: `python -m uv run pytest bot/tests/test_handlers_guardian.py --reuse-db -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add bot/keyboards/guardian.py bot/handlers/guardian.py bot/factory.py bot/tests/conftest.py bot/strings.py bot/tests/test_handlers_guardian.py
git commit -m "feat(bot): /wards ward management (menu + revoke), router wired"
```

---

### Task 4: Bot ward settings pickers

**Files:**
- Modify: `bot/keyboards/guardian.py`, `bot/handlers/guardian.py`
- Test: `bot/tests/test_handlers_guardian.py` (append)

**Interfaces:**
- Consumes: `ward_profile`, `WORDS_PRESETS`/`MORNING_PRESETS`/`EXAM_PRESETS`, `EN_VOICES`/`UZ_VOICES`, `voice_label`.
- Produces: `ward_settings_keyboard(profile, lid)`; edit pickers; save handler `wsv:<lid>:<field>:<value>`; weekday toggle `wsd:<lid>:<i|all|done>`.

- [ ] **Step 1: Write the failing test**

```python
# bot/tests/test_handlers_guardian.py  (append)
@pytest.mark.asyncio
async def test_wsv_saves_ward_words_only():
    guardian, learner = _guardian_with_ward()
    from apps.learning.models import LearningProfile
    LearningProfile.objects.create(user=learner, words_per_session=10)
    callback = AsyncMock()
    callback.data = f"wsv:{learner.id}:words:20"
    await gh.save_ward_value(callback, user=guardian)
    assert LearningProfile.objects.get(user=learner).words_per_session == 20


@pytest.mark.asyncio
async def test_wsv_rejects_non_guardian():
    outsider = User.objects.create(first_name="X")
    learner = User.objects.create(first_name="Kid")
    from apps.learning.models import LearningProfile
    LearningProfile.objects.create(user=learner, words_per_session=10)
    callback = AsyncMock()
    callback.data = f"wsv:{learner.id}:words:20"
    await gh.save_ward_value(callback, user=outsider)
    assert LearningProfile.objects.get(user=learner).words_per_session == 10  # unchanged
```

- [ ] **Step 2: Run to verify it fails** — Expected: FAIL (`save_ward_value` missing).

- [ ] **Step 3: Implement keyboards — append to `bot/keyboards/guardian.py`**

```python
from apps.common.tts import EN_VOICES, UZ_VOICES, voice_label
from bot.keyboards.common import EXAM_PRESETS, MORNING_PRESETS, WORDS_PRESETS


def _b(text, cb):
    return InlineKeyboardButton(text=text, callback_data=cb)


def ward_settings_keyboard(p, lid: int) -> InlineKeyboardMarkup:
    days = ", ".join(strings.WEEKDAY_SHORT[d] for d in p.study_weekdays)
    audio = strings.BTN_AUDIO_ON if p.audio_enabled else strings.BTN_AUDIO_OFF
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(f"🔤 {strings.SETTINGS_WORDS}: {p.words_per_session}", f"wsedit:{lid}:words")],
        [_b(f"📅 {strings.SETTINGS_DAYS}: {days}", f"wsedit:{lid}:days")],
        [_b(f"🌅 {strings.SETTINGS_MORNING}: {p.morning_time:%H:%M}", f"wsedit:{lid}:morning"),
         _b(f"🎯 {strings.SETTINGS_EXAM}: {p.exam_time:%H:%M}", f"wsedit:{lid}:exam")],
        [_b(f"🔊 {strings.SETTINGS_AUDIO}: {audio}", f"wsedit:{lid}:audio")],
        [_b(f"🇬🇧 {strings.SETTINGS_EN_VOICE}: {voice_label(p.en_voice)}", f"wsedit:{lid}:envoice")],
        [_b(f"🇺🇿 {strings.SETTINGS_UZ_VOICE}: {voice_label(p.uz_voice)}", f"wsedit:{lid}:uzvoice")],
        [_b(f"🔁 {strings.SETTINGS_REPEAT}: {p.audio_repeat}", f"wsedit:{lid}:repeat")],
    ])


def ward_picker(lid: int, field: str, p) -> InlineKeyboardMarkup:
    def row(pairs):
        return [_b(t, f"wsv:{lid}:{field}:{v}") for t, v in pairs]
    if field == "words":
        opts = [(str(n), n) for n in WORDS_PRESETS]
        return InlineKeyboardMarkup(inline_keyboard=[row(opts[i:i + 3]) for i in range(0, len(opts), 3)])
    if field in ("morning", "exam"):
        presets = MORNING_PRESETS if field == "morning" else EXAM_PRESETS
        return InlineKeyboardMarkup(inline_keyboard=[row([(t, i) for i, t in enumerate(presets)])])
    if field == "audio":
        return InlineKeyboardMarkup(inline_keyboard=[row([(strings.BTN_AUDIO_ON, "on"),
                                                          (strings.BTN_AUDIO_OFF, "off")])])
    if field == "repeat":
        return InlineKeyboardMarkup(inline_keyboard=[row([(str(n), n) for n in (1, 2, 3)])])
    if field in ("envoice", "uzvoice"):
        voices = EN_VOICES if field == "envoice" else UZ_VOICES
        return InlineKeyboardMarkup(inline_keyboard=[[_b(label, f"wsv:{lid}:{field}:{vid}")]
                                                     for vid, label in voices])
    # days handled by wsd:* toggle
    day_btns = [_b(("✅ " if i in p.study_weekdays else "") + name, f"wsd:{lid}:{i}")
                for i, name in enumerate(strings.WEEKDAY_SHORT)]
    rows = [day_btns[i:i + 4] for i in range(0, len(day_btns), 4)]
    rows.append([_b(strings.BTN_DONE, f"wsd:{lid}:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
```

- [ ] **Step 4: Implement handlers — append to `bot/handlers/guardian.py`**

```python
import datetime

from apps.relations.services.guardian import ward_profile
from bot.keyboards.common import EXAM_PRESETS, MORNING_PRESETS
from bot.keyboards.guardian import ward_picker, ward_settings_keyboard


async def _render_ward_settings(callback, user, lid):
    profile = await sync_to_async(ward_profile)(user, lid)
    if profile is None:
        return
    await callback.message.edit_text(
        strings.SETTINGS_TITLE, reply_markup=ward_settings_keyboard(profile, lid)
    )


# Replace the Task-3 stub body of open_ward_settings:
@router.callback_query(F.data.startswith("wset:"))
async def open_ward_settings(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    await _render_ward_settings(callback, user, int(callback.data.split(":")[1]))


@router.callback_query(F.data.startswith("wsedit:"))
async def edit_ward_field(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    _, lid_s, field = callback.data.split(":")
    lid = int(lid_s)
    profile = await sync_to_async(ward_profile)(user, lid)
    if profile is None:
        return
    await callback.message.edit_text(field, reply_markup=ward_picker(lid, field, profile))


def _apply_value(profile, field, value) -> list[str]:
    if field == "words":
        profile.words_per_session = int(value); return ["words_per_session"]
    if field == "repeat":
        profile.audio_repeat = int(value); return ["audio_repeat"]
    if field == "audio":
        profile.audio_enabled = value == "on"; return ["audio_enabled"]
    if field == "envoice":
        profile.en_voice = value; return ["en_voice"]
    if field == "uzvoice":
        profile.uz_voice = value; return ["uz_voice"]
    if field in ("morning", "exam"):
        presets = MORNING_PRESETS if field == "morning" else EXAM_PRESETS
        hhmm = presets[int(value)]
        t = datetime.datetime.strptime(hhmm, "%H:%M").time()
        if field == "morning":
            profile.morning_time = t; return ["morning_time"]
        profile.exam_time = t; return ["exam_time"]
    return []


@router.callback_query(F.data.startswith("wsv:"))
async def save_ward_value(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    _, lid_s, field, value = callback.data.split(":", 3)
    lid = int(lid_s)
    profile = await sync_to_async(ward_profile)(user, lid)
    if profile is None:
        return
    fields = _apply_value(profile, field, value)
    if fields:
        await sync_to_async(profile.save)(update_fields=[*fields, "updated_at"])
    await _render_ward_settings(callback, user, lid)


@router.callback_query(F.data.startswith("wsd:"))
async def toggle_ward_day(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    _, lid_s, arg = callback.data.split(":")
    lid = int(lid_s)
    profile = await sync_to_async(ward_profile)(user, lid)
    if profile is None:
        return
    if arg == "done":
        await _render_ward_settings(callback, user, lid)
        return
    i = int(arg)
    days = set(profile.study_weekdays)
    days.symmetric_difference_update({i})
    profile.study_weekdays = sorted(days)
    await sync_to_async(profile.save)(update_fields=["study_weekdays", "updated_at"])
    await callback.message.edit_reply_markup(reply_markup=ward_picker(lid, "days", profile))
```

Remove the Task-3 stub `open_ward_settings` (this task defines the real one).

- [ ] **Step 5: Run tests** — Expected: PASS.
- [ ] **Step 6: Commit**

```bash
git add bot/keyboards/guardian.py bot/handlers/guardian.py bot/tests/test_handlers_guardian.py
git commit -m "feat(bot): guardian edits each ward's settings (inline pickers)"
```

---

### Task 5: Web API — wards + ward settings

**Files:**
- Modify: `apps/catalog/views.py`, `config/urls.py`
- Test: `apps/catalog/tests/test_webapp_wards.py`

**Interfaces:**
- Produces: `api_wards(request)`; `api_ward_settings(request, learner_id)`. Routes `webapp/api/wards/`, `webapp/api/ward/<int:learner_id>/settings/`.

- [ ] **Step 1: Write the failing test**

```python
# apps/catalog/tests/test_webapp_wards.py
import hashlib, hmac, json, time
from urllib.parse import urlencode

import pytest

from apps.accounts.models import TelegramAccount, User
from apps.learning.models import LearningProfile
from apps.relations.models import Guardianship

TOKEN = "123:TESTTOKEN"
pytestmark = pytest.mark.django_db


def _init_data(uid):
    fields = {"auth_date": str(int(time.time())),
              "user": json.dumps({"id": uid, "first_name": "G"}, separators=(",", ":"))}
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
    other = User.objects.create(first_name="Z"); LearningProfile.objects.create(user=other)
    r = client.get(f"/webapp/api/ward/{other.id}/settings/", HTTP_X_TELEGRAM_INIT_DATA=_init_data(700))
    assert r.status_code == 403  # not this guardian's ward


def test_ward_settings_get_and_post(client, settings):
    settings.BOT_TOKEN = TOKEN
    _guardian, learner = _guardian_ward()
    auth = _init_data(700)
    got = client.get(f"/webapp/api/ward/{learner.id}/settings/", HTTP_X_TELEGRAM_INIT_DATA=auth)
    assert got.json()["words_per_session"] == 10
    client.post(f"/webapp/api/ward/{learner.id}/settings/",
                data=json.dumps({"words_per_session": 25}), content_type="application/json",
                HTTP_X_TELEGRAM_INIT_DATA=auth)
    assert LearningProfile.objects.get(user=learner).words_per_session == 25
```

- [ ] **Step 2: Run to verify it fails** — Expected: FAIL (routes/views missing).

- [ ] **Step 3: Implement — `apps/catalog/views.py`**

Add import: `from apps.relations.services.guardian import active_guardianship, ward_profile` and `from apps.relations.services.reports import guardian_wards`.

```python
@csrf_exempt
def api_wards(request):
    profile = _profile_from_request(request)
    if profile is None:
        return JsonResponse({"error": "unauthorized"}, status=401)
    wards = guardian_wards(profile.user)
    return JsonResponse({"wards": [{"id": w.id, "name": w.full_name or str(w.pk)} for w in wards]})


@csrf_exempt
def api_ward_settings(request, learner_id: int):
    caller = _profile_from_request(request)
    if caller is None:
        return JsonResponse({"error": "unauthorized"}, status=401)
    profile = ward_profile(caller.user, learner_id)
    if profile is None:
        return JsonResponse({"error": "forbidden"}, status=403)
    if request.method == "POST":
        try:
            payload = json.loads(request.body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "bad json"}, status=400)
        updates = _clean_settings(payload if isinstance(payload, dict) else {})
        if updates:
            for key, value in updates.items():
                setattr(profile, key, value)
            profile.save(update_fields=[*updates.keys(), "updated_at"])
    return JsonResponse(_profile_payload(profile))
```

- [ ] **Step 4: Routes — `config/urls.py`**

```python
    path("webapp/api/wards/", catalog_views.api_wards, name="webapp_wards"),
    path("webapp/api/ward/<int:learner_id>/settings/", catalog_views.api_ward_settings,
         name="webapp_ward_settings"),
```

- [ ] **Step 5: Run tests** — Expected: PASS (4).
- [ ] **Step 6: Commit**

```bash
git add apps/catalog/views.py config/urls.py apps/catalog/tests/test_webapp_wards.py
git commit -m "feat(webapp): guardian wards + ward-settings API (initData + guard)"
```

---

### Task 6: Web SPA — Nazorat section in Profil

**Files:**
- Modify: `templates/webapp/index.html`

- [ ] **Step 1: Implement**

In `showProfile()` (after `loadSettings()`), append a guardian section that loads wards and, when non-empty, renders a "👨‍👩‍👧 Nazorat" card. Add functions near `apiProfile`:

```javascript
    async function apiWards() { return getJSON("api/wards/"); }
    async function apiWardSettings(id, method, body) {
      const res = await fetch(`/webapp/api/ward/${id}/settings/`, {
        method, headers: { "Content-Type": "application/json", "X-Telegram-Init-Data": initData },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) throw new Error(res.status);
      return res.json();
    }
    async function loadWards() {
      const box = document.getElementById("wards");
      if (!box || !initData) return;
      let wards = [];
      try { wards = (await apiWards()).wards || []; } catch (e) { return; }
      if (!wards.length) return;  // not a guardian → show nothing
      box.innerHTML = `<div class="rounded-2xl bg-card border border-line p-5 space-y-2">
        <div class="text-sm font-semibold">👨‍👩‍👧 Nazorat</div>` +
        wards.map((w) => `<button data-id="${w.id}" data-name="${esc(w.name)}" class="js-ward w-full text-left rounded-xl bg-line/40 px-3 py-2 text-sm">${esc(w.name)} ⚙️</button>`).join("") +
        `</div>`;
      box.querySelectorAll(".js-ward").forEach((el) => el.addEventListener("click", () =>
        showWardSettings(el.dataset.id, el.dataset.name)));
    }
    async function showWardSettings(id, name) {
      setHeader(name, "O'quvchi sozlamalari"); setBack(() => showProfile());
      loading();
      const s = await apiWardSettings(id, "GET");
      setContent("px-4 py-4 pb-24", `<div id="settings">${settingsHTML(s)}</div>`);
      bindWardSettings(id, s);
    }
    function bindWardSettings(id, s) {
      bindSettings(s);                       // reuse day/toggle wiring
      const btn = document.getElementById("js-save");
      const clone = btn.cloneNode(true); btn.replaceWith(clone);  // drop the self-POST handler
      clone.addEventListener("click", async () => {
        clone.textContent = "Saqlanmoqda…"; clone.disabled = true;
        try {
          await apiWardSettings(id, "POST", {
            study_weekdays: s.study_weekdays,
            words_per_session: Number(document.getElementById("js-wps").value),
            morning_time: document.getElementById("js-morning").value,
            exam_time: document.getElementById("js-exam").value,
            audio_enabled: document.getElementById("js-audio").dataset.on === "1",
            audio_repeat: Number(document.getElementById("js-rep").value),
            en_voice: document.getElementById("js-envoice").value,
            uz_voice: document.getElementById("js-uzvoice").value,
            nudges_enabled: document.getElementById("js-nudge").dataset.on === "1",
          });
          clone.textContent = "✅ Saqlandi";
        } catch (e) { clone.textContent = "❌ Xato"; }
        setTimeout(() => { clone.textContent = "💾 Saqlash"; clone.disabled = false; }, 1300);
      });
    }
```

Add `<div id="wards"></div>` to the Profil content (after the `<div id="settings">…`), and call `loadWards();` at the end of `showProfile()`.

- [ ] **Step 2: Verify (curl — no browser)**

```bash
docker compose up -d db web  # local
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8001/webapp/  # 200
```
(Full visual check happens live after deploy.)

- [ ] **Step 3: Commit**

```bash
git add templates/webapp/index.html
git commit -m "feat(webapp): Nazorat section — guardian edits ward settings in Profil"
```

---

### Task 7: Integration + deploy

- [ ] **Step 1: Full suite + lint**

Run: `python -m uv run pytest --reuse-db && python -m uv run ruff check .`
Expected: all green, ruff clean.

- [ ] **Step 2: Merge + deploy**

```bash
git checkout main && git merge --no-ff guardian-management && git push origin main
```
Watch CI (`gh run watch`). Migration: none new. No `.env` change needed.

- [ ] **Step 3: Live verify**

- Bot: as a guardian, `/wards` → ward → ⚙️ Sozlamalar → change words/day → confirm the ward's next delivery reflects it. `🗑 Ajratish` revokes.
- Mini App: Profil → Nazorat → ward → edit + save.
- A fresh redeem (`?start=g<token>`) notifies the guardian.

---

## Notes

- All ward access is guarded by `active_guardianship`; the Task-3/4/5 tests include a non-guardian negative case each.
- ③ (dashboards) extends the Nazorat section with charts (learned words, exam-error words, missed days).
