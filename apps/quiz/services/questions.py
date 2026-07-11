import random

from apps.catalog.models import Word


def sample_words(unit_ids: list[int], count: int) -> list[Word]:
    """Up to `count` random words from the given units."""
    pool = list(Word.objects.filter(unit_id__in=unit_ids).select_related("unit__book"))
    if len(pool) <= count:
        random.shuffle(pool)
        return pool
    return random.sample(pool, count)
