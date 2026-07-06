import datetime
import json
from unittest.mock import AsyncMock, MagicMock

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import settings as st
from bot.states.onboarding import OnboardingStates


def _state():
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=0, chat_id=1, user_id=1))


def _profile():
    return MagicMock(
        words_per_session=10, study_weekdays=[0, 1, 2], morning_time=datetime.time(7, 0),
        exam_time=datetime.time(20, 0), audio_enabled=True, audio_repeat=2,
    )


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
