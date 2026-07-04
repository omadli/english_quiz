from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import User
from apps.relations.models import Guardianship, ReferralToken
from apps.relations.services.referral import create_referral_token
from apps.relations.services.reports import build_learner_report, guardian_wards
from bot import strings
from bot.keyboards.relations import wards_keyboard

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


@router.message(Command("report"))
async def cmd_report(message: Message, user: User) -> None:
    wards = await sync_to_async(guardian_wards)(user)
    if not wards:
        await message.answer(strings.NO_WARDS)
        return
    if len(wards) == 1:
        text = await sync_to_async(build_learner_report)(wards[0], timezone.localdate())
        await message.answer(text)
        return
    await message.answer(strings.PICK_WARD, reply_markup=wards_keyboard(wards))


@router.callback_query(F.data.startswith("rep:"))
async def pick_ward_report(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    learner_id = int(callback.data.split(":")[-1])
    linked = await sync_to_async(
        Guardianship.objects.filter(
            guardian=user, learner_id=learner_id, status=Guardianship.Status.ACTIVE
        ).exists
    )()
    if not linked:
        return
    learner = await sync_to_async(_get_learner)(learner_id)
    text = await sync_to_async(build_learner_report)(learner, timezone.localdate())
    await callback.message.answer(text)


def _get_learner(learner_id: int) -> User:
    return User.objects.get(pk=learner_id)
