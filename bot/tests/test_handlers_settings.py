import datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from apps.common.tts import EN_VOICES
from bot.handlers import settings as st
from bot.keyboards.settings import en_voice_keyboard, settings_keyboard
from bot.states.onboarding import OnboardingStates


def _state():
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=0, chat_id=1, user_id=1))


def _profile():
    return MagicMock(
        words_per_session=10, study_weekdays=[0, 1, 2], morning_time=datetime.time(7, 0),
        exam_time=datetime.time(20, 0), audio_enabled=True, audio_repeat=2,
        en_voice="en-US-AriaNeural", uz_voice="uz-UZ-MadinaNeural", nudges_enabled=True,
    )


def _wrap_sync_to_async(fn):
    async def _inner(*a, **k):
        return fn(*a, **k)
    return _inner


def test_settings_keyboard_shows_current_values():
    texts = [b.text for row in settings_keyboard(_profile()).inline_keyboard for b in row]
    assert any("10" in t for t in texts)       # words per session
    assert any("Aria" in t for t in texts)     # EN voice label
    assert any("Madina" in t for t in texts)   # UZ voice label


def test_en_voice_keyboard_lists_all_voices():
    cbs = [b.callback_data for row in en_voice_keyboard().inline_keyboard for b in row]
    for vid, _label in EN_VOICES:
        assert f"envoice:{vid}" in cbs


@patch("bot.handlers.settings.voice_sample", return_value=None)  # no real TTS in the test
@patch("bot.handlers.settings.sync_to_async", side_effect=_wrap_sync_to_async)
async def test_save_en_voice_updates_and_rerenders(_mock_sta, _mock_sample):
    profile = _profile()
    callback = AsyncMock()
    callback.data = "envoice:en-US-GuyNeural"
    await st.save_en_voice(callback, profile=profile)
    assert profile.en_voice == "en-US-GuyNeural"
    callback.message.edit_text.assert_awaited()


@patch("bot.handlers.settings.sync_to_async", side_effect=_wrap_sync_to_async)
async def test_save_repeat_updates(_mock_sta):
    profile = _profile()
    callback = AsyncMock()
    callback.data = "repeat:3"
    await st.save_repeat(callback, profile=profile)
    assert profile.audio_repeat == 3


def test_format_profile_shows_values():
    text = st.format_profile(_profile())
    assert "10" in text
    assert "07:00" in text


async def test_settings_command_shows_summary():
    message = AsyncMock()
    await st.cmd_settings(message, _state(), profile=_profile())
    message.answer.assert_awaited()


async def test_edit_words_enters_words_state():
    callback = AsyncMock()
    callback.data = "set:words"
    state = _state()
    await st.edit_words(callback, state, profile=_profile())
    assert await state.get_state() == OnboardingStates.words.state
    assert (await state.get_data())["words_per_session"] == 10


async def test_edit_audio_seeds_all_fields():
    callback = AsyncMock()
    callback.data = "set:audio"
    state = _state()
    await st.edit_audio(callback, state, profile=_profile())
    data = await state.get_data()
    # Seeded state is JSON-serialized by the production RedisStorage; the
    # profile's TimeField values must be seeded as "HH:MM" strings.
    json.dumps(data)
    assert data["words_per_session"] == 10
    assert data["study_weekdays"] == [0, 1, 2]
    assert data["morning_time"] == "07:00"
    assert data["exam_time"] == "20:00"
    assert data["audio_enabled"] is True
    assert data["audio_repeat"] == 2
