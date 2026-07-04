from django.utils import timezone

from apps.learning.models import DailySession, LearningProfile, SessionWord, WordProgress
from apps.learning.services.audio import build_word_audio
from apps.learning.services.cards import render_daily_card
from apps.learning.services.delivery import advance_position, next_words
from bot.sender import send_daily


def _local_date(profile: LearningProfile):
    from zoneinfo import ZoneInfo

    return timezone.now().astimezone(ZoneInfo(profile.timezone)).date()


def _caption(word) -> str:
    parts = [f"<b>{word.en}</b> {word.part_of_speech}".strip()]
    if word.pronunciation:
        parts.append(word.pronunciation)
    parts.append(f"🇺🇿 {word.uz}")
    if word.definition:
        parts.append(f"\n<i>{word.definition}</i>")
    if word.example:
        parts.append(word.example)
    return "\n".join(parts)


def run_delivery(user_id: int) -> DailySession | None:
    profile = (
        LearningProfile.objects.select_related("user", "current_unit__book")
        .filter(user_id=user_id, is_active=True, onboarded=True)
        .first()
    )
    if profile is None:
        return None
    account = getattr(profile.user, "telegram", None)
    if account is None or account.blocked_bot:
        return None

    date = _local_date(profile)
    session, _created = DailySession.objects.get_or_create(
        user_id=user_id,
        date=date,
        defaults={"book": profile.current_book, "unit": profile.current_unit},
    )
    if session.status == DailySession.Status.DELIVERED:
        return None

    words = next_words(profile, profile.words_per_session)
    if not words:
        # Course finished — nothing left to deliver; send nothing, leave session pending.
        return None

    items = []
    for order, word in enumerate(words, start=1):
        SessionWord.objects.get_or_create(
            daily_session=session, word=word, defaults={"order": order}
        )
        WordProgress.objects.get_or_create(user_id=user_id, word=word)
        image = word.image.read() if word.image else None
        audio = build_word_audio(word, profile.audio_repeat) if profile.audio_enabled else None
        items.append({"caption": _caption(word), "image": image, "audio": audio})

    card = render_daily_card(words, date)
    send_daily(account.telegram_id, card, items)

    advance_position(profile, words[-1])
    session.status = DailySession.Status.DELIVERED
    session.delivered_at = timezone.now()
    session.save(update_fields=["status", "delivered_at", "updated_at"])
    return session
