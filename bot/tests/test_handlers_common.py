from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import common

pytestmark = pytest.mark.asyncio


def _state():
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=0, chat_id=1, user_id=1))


async def test_help_replies():
    message = AsyncMock()
    await common.cmd_help(message)
    message.answer.assert_awaited()


async def test_cancel_with_active_state_clears():
    state = _state()
    from bot.states.onboarding import OnboardingStates
    await state.set_state(OnboardingStates.words)
    message = AsyncMock()
    await common.cmd_cancel(message, state)
    assert await state.get_state() is None
    message.answer.assert_awaited()


async def test_cancel_with_no_state():
    message = AsyncMock()
    await common.cmd_cancel(message, _state())
    message.answer.assert_awaited()
