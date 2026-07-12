import html

from aiogram.exceptions import TelegramForbiddenError
from django.conf import settings as dj_settings
from django.utils import timezone

from apps.learning.models import DailySession, LearningProfile, SessionWord, WordProgress
from apps.learning.services.audio import build_daily_audio
from apps.learning.services.delivery import advance_position, next_words
from bot.sender import send_daily


def _local_date(profile: LearningProfile):
    from zoneinfo import ZoneInfo

    return timezone.now().astimezone(ZoneInfo(profile.timezone)).date()


def _word_list_caption(words) -> str:
    """The morning message body: a numbered list of `word [IPA] — translation`."""
    lines = ["📅 <b>Bugungi so'zlar</b>", ""]
    for i, w in enumerate(words, 1):
        ipa = f" <i>{html.escape(w.pronunciation)}</i>" if w.pronunciation else ""
        lines.append(f"{i}. <b>{html.escape(w.en)}</b>{ipa} — {html.escape(w.uz)}")
    lines.append("")
    lines.append("🔊 Audio: inglizcha talaffuz + o'zbekcha tarjima")
    return "\n".join(lines)


def _webapp_today_url() -> str | None:
    base = dj_settings.WEBAPP_URL
    if not base:
        return None
    return f"{base}{'&' if '?' in base else '?'}view=today"


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
        # Course finished — nothing left to deliver; leave the session pending.
        return None

    for order, word in enumerate(words, start=1):
        SessionWord.objects.get_or_create(
            daily_session=session, word=word, defaults={"order": order}
        )
        WordProgress.objects.get_or_create(user_id=user_id, word=word)

    audio = (
        build_daily_audio(words, profile.en_voice, profile.uz_voice, profile.audio_repeat)
        if profile.audio_enabled
        else None
    )
    try:
        send_daily(account.telegram_id, _word_list_caption(words), audio, _webapp_today_url())
    except TelegramForbiddenError:
        account.blocked_bot = True
        account.save(update_fields=["blocked_bot", "updated_at"])
        return None

    advance_position(profile, words[-1])
    session.status = DailySession.Status.DELIVERED
    session.delivered_at = timezone.now()
    session.save(update_fields=["status", "delivered_at", "updated_at"])
    return session


def _today_session(user_id: int):
    profile = LearningProfile.objects.select_related("user").filter(user_id=user_id).first()
    if profile is None:
        return None, None
    date = _local_date(profile)
    return profile, DailySession.objects.filter(user_id=user_id, date=date).first()


def today_session_words(user_id: int) -> list:
    """Today's daily-session words (ordered), or [] if there's no session yet."""
    _profile, session = _today_session(user_id)
    if session is None:
        return []
    return [
        sw.word
        for sw in session.session_words.select_related("word__unit__book").order_by("order")
    ]


def today_session_payload(user_id: int):
    """Rebuild today's (caption, audio) so 'Bugungi vazifa' can re-send the morning task."""
    profile, session = _today_session(user_id)
    if session is None:
        return None
    words = [
        sw.word
        for sw in session.session_words.select_related("word__unit__book").order_by("order")
    ]
    if not words:
        return None
    audio = (
        build_daily_audio(words, profile.en_voice, profile.uz_voice, profile.audio_repeat)
        if profile.audio_enabled
        else None
    )
    return _word_list_caption(words), audio
