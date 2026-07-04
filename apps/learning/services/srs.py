import datetime

from django.utils import timezone

from apps.learning.models import WordProgress

MIN_EASE = 1.3


def apply_sm2(progress: WordProgress, correct: bool) -> None:
    """Update a WordProgress in place using the SM-2 algorithm, then save."""
    if correct:
        progress.repetitions += 1
        if progress.repetitions == 1:
            progress.interval_days = 1
        elif progress.repetitions == 2:
            progress.interval_days = 6
        else:
            progress.interval_days = round(progress.interval_days * progress.ease_factor)
        progress.ease_factor = progress.ease_factor + 0.1
        progress.correct_count += 1
    else:
        progress.repetitions = 0
        progress.interval_days = 1
        progress.ease_factor = max(MIN_EASE, progress.ease_factor - 0.2)
        progress.wrong_count += 1

    today = timezone.now().date()
    progress.next_review = today + datetime.timedelta(days=progress.interval_days)
    progress.status = (
        WordProgress.Status.KNOWN if progress.repetitions >= 3 else WordProgress.Status.LEARNING
    )
    progress.last_reviewed = timezone.now()
    progress.save()


def grade_answer(user, word, correct: bool) -> WordProgress:
    progress, _ = WordProgress.objects.get_or_create(user=user, word=word)
    apply_sm2(progress, correct)
    return progress
