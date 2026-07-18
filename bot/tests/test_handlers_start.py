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
    assert kwargs.get("reply_markup") is not None  # returning users get the main menu


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


@patch("bot.handlers.start.load_quiz")
@patch("bot.handlers.start.fulfill_login_request", return_value="654321")
async def test_start_login_deeplink_dms_code_and_skips_onboarding(mock_fulfill, mock_load):
    user = MagicMock()
    message = AsyncMock()
    await start_handler.cmd_start(
        message, _state(), _cmd(args="login_NONCE123"), user=user, profile=MagicMock()
    )
    mock_fulfill.assert_called_once_with("NONCE123", user)
    mock_load.assert_not_called()  # login_ is handled before quiz-code decoding
    assert "654321" in message.answer.call_args.args[0]


@patch("bot.handlers.start.fulfill_login_request", return_value=None)
async def test_start_login_deeplink_expired(mock_fulfill):
    message = AsyncMock()
    await start_handler.cmd_start(
        message, _state(), _cmd(args="login_STALE"), user=MagicMock(), profile=MagicMock()
    )
    message.answer.assert_awaited()  # sends the "expired" string, no crash


_CFG = {"book_id": 1, "unit_ids": [10], "count": 15, "interval": 20, "types": ["en_uz"]}


@patch("bot.handlers.start.asyncio.create_task")
@patch("bot.handlers.start.start_shared_quiz", new_callable=MagicMock)
@patch("bot.handlers.start.load_quiz")
async def test_start_code_deep_link_launches_shared_quiz(mock_load, mock_launch, mock_task):
    """`?start=<code>` decodes the config and schedules the shared quiz, skipping onboarding."""
    mock_load.return_value = _CFG
    message = AsyncMock()
    message.chat.id = 777

    await start_handler.cmd_start(
        message, _state(), _cmd(args="b1u1c15t20qE"), user=MagicMock(), profile=MagicMock()
    )

    mock_load.assert_called_once_with("b1u1c15t20qE")
    mock_launch.assert_called_once_with(message.bot, 777, [10], 15, 20, ["en_uz"])
    mock_task.assert_called_once()
    mock_task.call_args.args[0].close()  # close the un-awaited coroutine


@patch("bot.handlers.start.seed_group_quiz_from_config", new_callable=AsyncMock)
@patch("bot.handlers.start.load_quiz")
async def test_start_code_deep_link_in_group_seeds_group(mock_load, mock_seed):
    """`?startgroup=<code>` (delivered as /start in a group) seeds a group quiz."""
    mock_load.return_value = _CFG
    message = AsyncMock()
    message.chat.id = -100
    message.chat.type = "supergroup"
    message.from_user.id = 555

    await start_handler.cmd_start(
        message, _state(), _cmd(args="b1u1c15t20qE"), user=MagicMock(), profile=MagicMock()
    )
    mock_seed.assert_awaited_once_with(message.bot, -100, 555, _CFG)


@patch("bot.handlers.start.start_shared_quiz", new_callable=MagicMock)
@patch("bot.handlers.start.load_quiz", return_value=None)
async def test_start_bad_code_falls_through(mock_load, mock_launch):
    """An undecodable/unknown code doesn't launch — falls through to the normal welcome."""
    profile = MagicMock(onboarded=True)
    message = AsyncMock()
    # non-"g" payload so it doesn't hit the referral path; load_quiz mocked to None
    await start_handler.cmd_start(
        message, _state(), _cmd(args="xyz123"), user=MagicMock(), profile=profile
    )
    mock_launch.assert_not_called()
    message.answer.assert_awaited()  # got the welcome-back instead


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
