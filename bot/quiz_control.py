"""Pause / resume / stop control for a live quiz, keyed by chat_id.

Native Telegram quiz polls can't be paused once sent (``open_period`` is
server-side), so a pause only takes effect at the *question boundary*: the
current poll runs out, then the runner blocks before sending the next one.

# ponytail: in-memory registry — one polling bot process, like
# quiz_practice._pending / group_quiz._ready. Move to Redis for replicas.
"""

import asyncio

_controls: dict[int, "QuizControl"] = {}


class QuizControl:
    def __init__(self) -> None:
        self._resume = asyncio.Event()
        self._resume.set()  # start un-paused
        self.stopped = False

    @property
    def paused(self) -> bool:
        return not self._resume.is_set()

    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    def stop(self) -> None:
        self.stopped = True
        self._resume.set()  # unblock a paused runner so its loop can exit

    async def gate(self) -> bool:
        """Block while paused; return True if the runner should keep going."""
        await self._resume.wait()
        return not self.stopped


def new_control(chat_id: int) -> QuizControl:
    control = QuizControl()
    _controls[chat_id] = control
    return control


def get_control(chat_id: int) -> "QuizControl | None":
    return _controls.get(chat_id)


def clear_control(chat_id: int) -> None:
    _controls.pop(chat_id, None)
