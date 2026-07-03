from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from asgiref.sync import sync_to_async

from bot.services.users import get_or_create_user


class UserMiddleware(BaseMiddleware):
    """Inject the Django User + LearningProfile for the acting Telegram user."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is not None:
            user, profile, _ = await sync_to_async(get_or_create_user)(
                telegram_id=tg_user.id,
                username=tg_user.username or "",
                first_name=tg_user.first_name or "",
                last_name=tg_user.last_name or "",
                language_code=tg_user.language_code or "",
            )
            data["user"] = user
            data["profile"] = profile
        return await handler(event, data)
