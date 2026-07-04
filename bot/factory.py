from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from bot.config import get_bot_token, get_fsm_redis_url
from bot.handlers import (
    books,
    common,
    group_quiz,
    leaderboard,
    onboarding,
    quiz,
    relations,
    settings,
    start,
)
from bot.middlewares.user import UserMiddleware


def build_bot() -> Bot:
    return Bot(token=get_bot_token(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=RedisStorage.from_url(get_fsm_redis_url()))
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())
    dp.include_router(start.router)
    dp.include_router(onboarding.router)
    dp.include_router(settings.router)
    dp.include_router(common.router)
    dp.include_router(quiz.router)
    dp.include_router(group_quiz.router)
    dp.include_router(relations.router)
    dp.include_router(leaderboard.router)
    dp.include_router(books.router)
    return dp
