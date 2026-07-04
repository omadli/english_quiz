from django.db.models import Q

from apps.catalog.models import Word
from apps.learning.models import LearningProfile

_ORDER = ("unit__book__number", "unit__number", "order")


def next_words(profile: LearningProfile, count: int) -> list[Word]:
    """Return the next `count` words after the profile's position, in global order."""
    qs = Word.objects.select_related("unit__book")
    if profile.current_unit_id is not None:
        unit = profile.current_unit
        bn, un, order = unit.book.number, unit.number, profile.current_word_order
        after = (
            Q(unit__book__number__gt=bn)
            | (Q(unit__book__number=bn) & Q(unit__number__gt=un))
            | (Q(unit__book__number=bn) & Q(unit__number=un) & Q(order__gt=order))
        )
        qs = qs.filter(after)
    return list(qs.order_by(*_ORDER)[:count])


def advance_position(profile: LearningProfile, word: Word) -> None:
    """Move the profile's position to `word`."""
    profile.current_book = word.unit.book
    profile.current_unit = word.unit
    profile.current_word_order = word.order
    profile.save(update_fields=["current_book", "current_unit", "current_word_order", "updated_at"])
