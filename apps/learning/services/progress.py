from apps.accounts.models import TelegramAccount
from apps.learning.models import LearnedWord


def mark_learned(user, word_ids: list[int]) -> int:
    """Mark words as learned for `user` who just completed a test/exam on them.

    Completing a test (bot quiz OR Mini App exam) is the ONLY way words become
    'learned' — manual marking was removed. Returns the newly-marked count.
    """
    if not word_ids:
        return 0
    already = set(
        LearnedWord.objects.filter(user=user, word_id__in=word_ids)
        .values_list("word_id", flat=True)
    )
    fresh = [wid for wid in dict.fromkeys(word_ids) if wid not in already]
    LearnedWord.objects.bulk_create(
        [LearnedWord(user=user, word_id=wid) for wid in fresh], ignore_conflicts=True
    )
    return len(fresh)


def mark_words_learned(telegram_id: int, word_ids: list[int]) -> int:
    """`mark_learned` keyed by telegram_id. No-op for an unknown user (e.g. a
    group chat_id)."""
    account = (
        TelegramAccount.objects.filter(telegram_id=telegram_id).select_related("user").first()
    )
    if account is None:
        return 0
    return mark_learned(account.user, word_ids)
