import random

from django.utils import timezone

from apps.catalog.models import Word
from apps.learning.models import DailySession, ExamQuestion, WordProgress

_TYPES = [ExamQuestion.QType.EN_UZ, ExamQuestion.QType.UZ_EN, ExamQuestion.QType.DEF_WORD]
_EXPLANATION = "@essential_words"


def select_exam_words(session: DailySession, review_cap: int) -> list[Word]:
    """The session's words plus up to review_cap SRS-due review words, deduped."""
    day_words = list(session.words.all())
    seen = {w.pk for w in day_words}
    today = timezone.now().date()
    due = (
        Word.objects.filter(progress__user=session.user, progress__next_review__lte=today)
        .exclude(progress__status=WordProgress.Status.NEW)
        .exclude(pk__in=seen)
        .distinct()
        .order_by("progress__next_review")[:review_cap]
    )
    return day_words + list(due)


def _distractors(word: Word, field: str, count: int) -> list[str]:
    """`count` distinct values of `field` from other words (same book first, else global)."""
    correct_value = getattr(word, field)

    def _pool(qs):
        return [
            v for v in qs.exclude(pk=word.pk).values_list(field, flat=True)
            if v and v != correct_value
        ]

    pool = list(dict.fromkeys(_pool(Word.objects.filter(unit__book=word.unit.book))))
    if len(pool) < count:
        extra = _pool(Word.objects.all())
        for v in dict.fromkeys(extra):
            if v not in pool:
                pool.append(v)
    random.shuffle(pool)
    return pool[:count]


def _question_for(word: Word, qtype: str) -> dict:
    if qtype == ExamQuestion.QType.EN_UZ:
        prompt = f"{word.en} {word.part_of_speech}".strip()
        correct = word.uz
        options = [correct, *_distractors(word, "uz", 3)]
    elif qtype == ExamQuestion.QType.UZ_EN:
        prompt = word.uz
        correct = word.en
        options = [correct, *_distractors(word, "en", 3)]
    else:  # DEF_WORD
        prompt = word.definition or word.en
        correct = word.en
        options = [correct, *_distractors(word, "en", 3)]

    random.shuffle(options)
    options = [o[:100] for o in options]
    correct_option = options.index(correct[:100])
    return {
        "word": word,
        "question_type": qtype,
        "prompt": prompt[:300],
        "options": options,
        "correct_option": correct_option,
        "explanation": _EXPLANATION,
    }


def build_questions(words: list[Word]) -> list[dict]:
    return [_question_for(word, _TYPES[i % 3]) for i, word in enumerate(words)]
