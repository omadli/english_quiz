from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import start as start_handler
from bot.states.onboarding import OnboardingStates


def _state():
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=0, chat_id=1, user_id=1))


def _cmd(args=None):
    return CommandObject(command="start", args=args)


pytestmark = pytest.mark.asyncio


async def test_start_new_user_shows_intro_and_no_state():
    profile = MagicMock(onboarded=False)
    message = AsyncMock()
    state = _state()
    await start_handler.cmd_start(message, state, _cmd(), user=MagicMock(), profile=profile)
    message.answer.assert_awaited()
    assert await state.get_state() is None


async def test_start_returning_user_gets_welcome_back():
    profile = MagicMock(onboarded=True)
    message = AsyncMock()
    await start_handler.cmd_start(message, _state(), _cmd(), user=MagicMock(), profile=profile)
    args, kwargs = message.answer.call_args
    assert "settings" in (args[0] if args else kwargs.get("text", "")).lower()


@patch("bot.handlers.start.redeem_token")
async def test_start_with_referral_payload_redeems(mock_redeem):
    mock_redeem.return_value = MagicMock()  # a Guardianship
    profile = MagicMock(onboarded=True)
    user = MagicMock()
    message = AsyncMock()
    await start_handler.cmd_start(
        message, _state(), _cmd(args="gABC123"), user=user, profile=profile
    )
    mock_redeem.assert_called_once_with("ABC123", user)
    assert message.answer.await_count >= 1


@patch("bot.handlers.start.redeem_token")
async def test_start_without_payload_does_not_redeem(mock_redeem):
    profile = MagicMock(onboarded=True)
    message = AsyncMock()
    await start_handler.cmd_start(message, _state(), _cmd(), user=MagicMock(), profile=profile)
    mock_redeem.assert_not_called()


async def test_begin_wizard_sets_first_state():
    callback = AsyncMock()
    state = _state()
    await start_handler.begin_wizard(callback, state)
    assert await state.get_state() == OnboardingStates.words.state
    callback.answer.assert_awaited()


@patch("bot.handlers.start.set_starting_position")
@patch("bot.handlers.start.update_profile")
async def test_use_defaults_onboards(mock_update, mock_setpos):
    profile = MagicMock()
    callback = AsyncMock()
    state = _state()
    await start_handler.use_defaults(callback, state, profile=profile)
    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["onboarded"] is True
    mock_setpos.assert_called_once_with(profile)
    assert await state.get_state() is None
