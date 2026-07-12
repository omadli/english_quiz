import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.relations.models import Guardianship
from bot.handlers import guardian as gh
from bot.keyboards.common import MORNING_PRESETS

# Async handler tests mock the guard/service layer (its DB logic is covered by
# apps/relations/tests/test_guardian_service.py) — keeps these free of async+DB friction.


async def test_cmd_wards_lists():
    with patch.object(gh, "guardian_wards", return_value=[MagicMock(pk=1, full_name="Kid")]):
        message = AsyncMock()
        await gh.cmd_wards(message, user=MagicMock())
    message.answer.assert_awaited()


async def test_cmd_wards_empty_says_none():
    with patch.object(gh, "guardian_wards", return_value=[]):
        message = AsyncMock()
        await gh.cmd_wards(message, user=MagicMock())
    said = [c.args[0] for c in message.answer.await_args_list if c.args]
    assert gh.strings.NO_WARDS in said


async def test_open_ward_shows_menu():
    link = MagicMock()
    link.learner.full_name = "Kid"
    link.learner_id = 5
    with patch.object(gh, "active_guardianship", return_value=link):
        callback = AsyncMock()
        callback.data = "ward:5"
        await gh.open_ward(callback, user=MagicMock())
    callback.message.edit_text.assert_awaited()


async def test_wset_rejects_non_guardian():
    with patch.object(gh, "ward_profile", return_value=None):
        callback = AsyncMock()
        callback.data = "wset:5"
        await gh.open_ward_settings(callback, user=MagicMock())
    callback.message.edit_text.assert_not_awaited()  # guard blocks


async def test_wrevoke_sets_revoked():
    with patch.object(gh, "revoke", return_value=True):
        callback = AsyncMock()
        callback.data = "wrevoke:5"
        await gh.do_revoke(callback, user=MagicMock())
    callback.message.edit_text.assert_awaited()


async def test_edit_ward_field_shows_picker():
    profile = MagicMock(study_weekdays=[0, 1])
    with patch.object(gh, "ward_profile", return_value=profile):
        callback = AsyncMock()
        callback.data = "wsedit:5:words"
        await gh.edit_ward_field(callback, user=MagicMock())
    callback.message.edit_text.assert_awaited()


async def test_wsv_saves_ward_value():
    profile = MagicMock(words_per_session=10)
    with patch.object(gh, "ward_profile", return_value=profile), \
         patch.object(gh, "_render_ward_settings", new_callable=AsyncMock):
        callback = AsyncMock()
        callback.data = "wsv:5:words:20"
        await gh.save_ward_value(callback, user=MagicMock())
    assert profile.words_per_session == 20
    profile.save.assert_called_once()


async def test_wsv_rejects_non_guardian():
    with patch.object(gh, "ward_profile", return_value=None):
        callback = AsyncMock()
        callback.data = "wsv:5:words:20"
        await gh.save_ward_value(callback, user=MagicMock())  # no crash, nothing saved
    callback.answer.assert_awaited()


def test_apply_value_morning_uses_preset_index():
    p = MagicMock()
    gh._apply_value(p, "morning", "1")
    assert p.morning_time == datetime.datetime.strptime(MORNING_PRESETS[1], "%H:%M").time()


def test_apply_value_voice_and_audio():
    p = MagicMock()
    assert gh._apply_value(p, "envoice", "en-US-GuyNeural") == ["en_voice"]
    assert p.en_voice == "en-US-GuyNeural"
    gh._apply_value(p, "audio", "off")
    assert p.audio_enabled is False


@pytest.mark.django_db
def test_guardian_notify_info_returns_tg_and_role():
    from apps.accounts.models import TelegramAccount, User
    from bot.handlers import start as start_handler

    guardian = User.objects.create(first_name="Mom")
    TelegramAccount.objects.create(user=guardian, telegram_id=8001)
    learner = User.objects.create(first_name="Kid")
    link = Guardianship.objects.create(guardian=guardian, learner=learner, role="parent")
    tg_id, role = start_handler._guardian_notify_info(link)
    assert tg_id == 8001
    assert "ota" in role.lower()


@pytest.mark.django_db
def test_guardian_notify_info_none_without_telegram():
    from apps.accounts.models import User
    from bot.handlers import start as start_handler

    guardian = User.objects.create(first_name="Mom")  # no TelegramAccount
    learner = User.objects.create(first_name="Kid")
    link = Guardianship.objects.create(guardian=guardian, learner=learner, role="teacher")
    assert start_handler._guardian_notify_info(link) is None
