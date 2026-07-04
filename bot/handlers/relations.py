from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.conf import settings

from apps.accounts.models import User
from apps.relations.models import ReferralToken
from apps.relations.services.referral import create_referral_token
from bot import strings

router = Router()


async def bot_username(bot: Bot) -> str:
    if settings.BOT_USERNAME:
        return settings.BOT_USERNAME
    me = await bot.get_me()
    return me.username


async def _send_link(message: Message, user: User, role: str, template: str) -> None:
    token = await sync_to_async(create_referral_token)(user, role)
    username = await bot_username(message.bot)
    link = f"https://t.me/{username}?start=g{token.token}"
    await message.answer(template.format(link=link))


@router.message(Command("parent"))
async def cmd_parent(message: Message, user: User) -> None:
    await _send_link(message, user, ReferralToken.Role.PARENT, strings.PARENT_LINK)


@router.message(Command("teacher"))
async def cmd_teacher(message: Message, user: User) -> None:
    await _send_link(message, user, ReferralToken.Role.TEACHER, strings.TEACHER_LINK)
