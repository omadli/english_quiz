from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from asgiref.sync import sync_to_async
from django.utils import timezone

from apps.accounts.models import User
from apps.learning.services.ranking import build_monthly_leaderboard, user_month_rank
from bot import strings

router = Router()

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _format_leaderboard(entries: list[dict], own_rank: tuple[int, int] | None) -> str:
    if not entries:
        return strings.TOP_EMPTY
    lines = [strings.TOP_TITLE]
    for e in entries:
        badge = _MEDALS.get(e["rank"], f"{e['rank']}.")
        lines.append(f"{badge} {e['name']} — {e['points']} ball ({e['sessions']} kun)")
    if own_rank is not None and own_rank[0] > len(entries):
        lines.append("")
        lines.append(strings.TOP_YOUR_RANK.format(rank=own_rank[0], points=own_rank[1]))
    return "\n".join(lines)


@router.message(Command("top"))
async def cmd_top(message: Message, user: User) -> None:
    now = timezone.localtime()
    entries = await sync_to_async(build_monthly_leaderboard)(now.year, now.month, 10)
    own = await sync_to_async(user_month_rank)(user, now.year, now.month)
    await message.answer(_format_leaderboard(entries, own))
