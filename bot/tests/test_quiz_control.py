import asyncio

import pytest

from bot.quiz_control import (
    QuizControl,
    clear_control,
    get_control,
    new_control,
)


@pytest.mark.asyncio
async def test_gate_passes_when_running():
    c = QuizControl()
    assert await c.gate() is True  # un-paused → keep going


@pytest.mark.asyncio
async def test_pause_blocks_until_resume():
    c = QuizControl()
    c.pause()
    assert c.paused
    task = asyncio.create_task(c.gate())
    await asyncio.sleep(0.01)
    assert not task.done()  # blocked while paused
    c.resume()
    assert await task is True  # resume unblocks, keep going


@pytest.mark.asyncio
async def test_stop_unblocks_and_signals_exit():
    c = QuizControl()
    c.pause()
    task = asyncio.create_task(c.gate())
    await asyncio.sleep(0.01)
    c.stop()  # must unblock a paused gate...
    assert await task is False  # ...and tell the loop to exit
    assert c.stopped


def test_registry_lifecycle():
    assert get_control(123) is None
    c = new_control(123)
    assert get_control(123) is c
    clear_control(123)
    assert get_control(123) is None
