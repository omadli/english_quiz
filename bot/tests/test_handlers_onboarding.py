import datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import onboarding as ob
from bot.states.onboarding import OnboardingStates


def _state():
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=0, chat_id=1, user_id=1))


def _cb(data):
    c = AsyncMock()
    c.data = data
    return c


async def test_pick_words_stores_and_advances_to_weekdays():
    state = _state()
    await state.set_state(OnboardingStates.words)
    await ob.pick_words(_cb("onb:words:15"), state)
    assert (await state.get_data())["words_per_session"] == 15
    assert await state.get_state() == OnboardingStates.weekdays.state


async def test_toggle_and_done_weekdays_advances_to_morning():
    state = _state()
    await state.set_state(OnboardingStates.weekdays)
    await ob.toggle_weekday_cb(_cb("onb:wd:0"), state)
    await ob.toggle_weekday_cb(_cb("onb:wd:2"), state)
    assert (await state.get_data())["study_weekdays"] == [0, 2]
    await ob.weekdays_done(_cb("onb:wd:done"), state)
    assert await state.get_state() == OnboardingStates.morning.state


async def test_everyday_selects_all():
    state = _state()
    await state.set_state(OnboardingStates.weekdays)
    await ob.weekdays_all(_cb("onb:wd:all"), state)
    assert (await state.get_data())["study_weekdays"] == [0, 1, 2, 3, 4, 5, 6]


async def test_pick_morning_preset_advances_to_exam():
    state = _state()
    await state.set_state(OnboardingStates.morning)
    await ob.pick_morning(_cb("onb:mt:06:00"), state)
    data = await state.get_data()
    # FSM state is JSON-serialized by the production RedisStorage, so times
    # must be stored as "HH:MM" strings, never datetime.time objects.
    json.dumps(data)
    assert data["morning_time"] == "06:00"
    assert await state.get_state() == OnboardingStates.exam.state


async def test_typed_morning_time_valid_advances():
    state = _state()
    await state.set_state(OnboardingStates.morning)
    msg = AsyncMock()
    msg.text = "06:45"
    await ob.typed_morning(msg, state)
    data = await state.get_data()
    json.dumps(data)
    assert data["morning_time"] == "06:45"
    assert await state.get_state() == OnboardingStates.exam.state


async def test_pick_exam_preset_stores_json_serializable_string():
    state = _state()
    await state.set_state(OnboardingStates.exam)
    await ob.pick_exam(_cb("onb:et:20:00"), state)
    data = await state.get_data()
    json.dumps(data)
    assert data["exam_time"] == "20:00"
    assert await state.get_state() == OnboardingStates.audio.state


async def test_typed_morning_time_invalid_reprompts():
    state = _state()
    await state.set_state(OnboardingStates.morning)
    msg = AsyncMock()
    msg.text = "99:99"
    await ob.typed_morning(msg, state)
    assert "morning_time" not in (await state.get_data())
    assert await state.get_state() == OnboardingStates.morning.state
    msg.answer.assert_awaited()


async def test_audio_off_skips_repeat_to_confirm():
    state = _state()
    await state.set_state(OnboardingStates.audio)
    await ob.pick_audio(_cb("onb:audio:off"), state)
    data = await state.get_data()
    assert data["audio_enabled"] is False
    assert data["audio_repeat"] == 0
    assert await state.get_state() == OnboardingStates.confirm.state


async def test_audio_on_goes_to_repeat():
    state = _state()
    await state.set_state(OnboardingStates.audio)
    await ob.pick_audio(_cb("onb:audio:on"), state)
    assert await state.get_state() == OnboardingStates.audio_repeat.state


@patch("bot.handlers.onboarding.apply_wizard_data")
async def test_save_persists_and_clears(mock_apply):
    profile = MagicMock()
    state = _state()
    await state.set_state(OnboardingStates.confirm)
    await state.update_data(
        words_per_session=10, study_weekdays=[0], morning_time=datetime.time(7, 0),
        exam_time=datetime.time(20, 0), audio_enabled=True, audio_repeat=2,
    )
    await ob.save_wizard(_cb("onb:save"), state, profile=profile)
    mock_apply.assert_called_once()
    assert await state.get_state() is None


def test_format_summary_contains_values():
    text = ob.format_summary({
        "words_per_session": 12, "study_weekdays": [0, 2], "morning_time": datetime.time(7, 0),
        "exam_time": datetime.time(20, 0), "audio_enabled": True, "audio_repeat": 2,
    })
    assert "12" in text
