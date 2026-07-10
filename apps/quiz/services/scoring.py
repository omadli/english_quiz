import html

from django.utils import timezone

from apps.common.emoji import custom_emoji
from apps.quiz.models import GroupQuizParticipant, GroupQuizQuestion

_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def record_group_answer(
    poll_id: str, option_ids: list[int], telegram_id: int, username: str, full_name: str
) -> bool:
    """Score a group-quiz poll answer. Returns False if poll_id is not a group question."""
    question = GroupQuizQuestion.objects.select_related("session").filter(poll_id=poll_id).first()
    if question is None:
        return False

    participant, _ = GroupQuizParticipant.objects.get_or_create(
        session=question.session,
        telegram_id=telegram_id,
        defaults={"username": username, "full_name": full_name},
    )
    if option_ids:
        if option_ids[0] == question.correct_option:
            participant.correct_count += 1
        if question.sent_at is not None:
            participant.total_time += (timezone.now() - question.sent_at).total_seconds()
    participant.save(update_fields=["correct_count", "total_time", "updated_at"])
    return True


def build_leaderboard(session) -> str:
    participants = sorted(
        session.participants.all(), key=lambda p: (-p.correct_count, p.total_time)
    )
    if not participants:
        return "🏁 Test yakunlandi! Hech kim ishtirok etmadi."

    lines = [f"{custom_emoji('finish', '🏁')} <b>Test yakunlandi!</b>", ""]
    for rank, p in enumerate(participants[:50], start=1):
        label = _MEDALS.get(rank, f"{rank}.")
        # Names are sent with parse_mode=HTML → escape user-controlled full_name
        # so a "<", ">" or "&" in it can't break the whole leaderboard send.
        name = f"@{p.username}" if p.username else html.escape(p.full_name) or str(p.telegram_id)
        lines.append(f"{label} {name} — <b>{p.correct_count}</b> ({p.total_time:.1f}s)")
    lines.append(f"\n{custom_emoji('trophy', '🏆')} G'oliblarni tabriklaymiz!")
    return "\n".join(lines)
