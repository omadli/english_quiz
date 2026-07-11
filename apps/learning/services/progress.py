from apps.accounts.models import TelegramAccount
from apps.learning.models import LearnedWord


def mark_words_learned(telegram_id: int, word_ids: list[int]) -> int:
    """Mark words as learned for a user who just completed a test on them.

    This is the ONLY way words become 'learned' (manual marking was removed).
    Returns the number of newly-marked words. No-op for an unknown user (e.g.
    a group chat_id) or empty list.
    """
    if not word_ids:
        return 0
    account = (
        TelegramAccount.objects.filter(telegram_id=telegram_id).select_related("user").first()
    )
    if account is None:
        return 0
    already = set(
        LearnedWord.objects.filter(user=account.user, word_id__in=word_ids)
        .values_list("word_id", flat=True)
    )
    fresh = [wid for wid in dict.fromkeys(word_ids) if wid not in already]
    LearnedWord.objects.bulk_create(
        [LearnedWord(user=account.user, word_id=wid) for wid in fresh], ignore_conflicts=True
    )
    return len(fresh)
