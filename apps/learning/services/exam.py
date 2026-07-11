import html
import random
import re

from django.conf import settings
from django.utils import timezone

from apps.catalog.models import Word
from apps.learning.models import DailySession, ExamQuestion, WordProgress

_TYPES = [ExamQuestion.QType.EN_UZ, ExamQuestion.QType.UZ_EN, ExamQuestion.QType.DEF_WORD]
_TAG_RE = re.compile(r"<[^>]+>")
_EXPL_LIMIT = 190  # Telegram poll explanation max is 200 chars; leave a margin


def _vislen(s: str) -> int:
    return len(_TAG_RE.sub("", s))


def word_explanation(word: Word) -> str:
    """Rich, formatted poll explanation for a word: en · pos · IPA · uz · definition
    · source (book/unit) · @bot. Kept within Telegram's 200-char explanation limit."""
    en = html.escape(word.en)
    pos = f" <i>{html.escape(word.part_of_speech)}</i>" if word.part_of_speech else ""
    ipa = f" <code>{html.escape(word.pronunciation)}</code>" if word.pronunciation else ""
    uz = f"\n🇺🇿 <b>{html.escape(word.uz[:70])}</b>" if word.uz else ""
    src = f"\n📖 Book {word.unit.book.number} · Unit {word.unit.number}"
    handle = f" · @{settings.BOT_USERNAME}" if settings.BOT_USERNAME else ""
    fixed = f"<b>{en}</b>{pos}{ipa}{uz}{src}{handle}"
    definition = ""
    budget = _EXPL_LIMIT - _vislen(fixed)
    if word.definition and budget > 12:
        d = word.definition.strip()
        d = (d[: budget - 1].rstrip() + "…") if len(d) > budget else d
        definition = f"\n💬 <i>{html.escape(d)}</i>"
    return f"<b>{en}</b>{pos}{ipa}{uz}{definition}{src}{handle}"


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
        prompt = word.en  # English question shows just the word (no part-of-speech)
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
        "explanation": word_explanation(word),
    }


def build_questions(words: list[Word], types: list[str] | None = None) -> list[dict]:
    active_types = types or _TYPES
    return [
        _question_for(word, active_types[i % len(active_types)])
        for i, word in enumerate(words)
    ]
