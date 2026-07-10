"""Self-contained quiz-share codes.

A quiz config (book, units, count, interval, question types) is packed into a
compact string using only ``[A-Za-z0-9_-]`` so the *same* code works as a
Telegram deep-link ``start``/``startgroup`` parameter (max 64 chars, that
charset only), an inline-query string, and inline-button payload.

Format: ``b<book>u<units>c<count>t<interval>q<types>``
  - units: sorted numbers range-compressed, ranges ``a-b``, singles joined ``_``
    e.g. ``1-4`` , ``1_3_5`` , ``1-3_7-8``
  - types: concatenated single chars — en_uz=E, uz_en=U, def_word=D

Overflow (a pathological scattered selection > 64 chars) falls back to a
``q<pk>`` token backed by the SharedQuiz row; ``load_quiz`` accepts both.
"""

import re

from apps.catalog.models import Book, Unit
from apps.quiz.models import SharedQuiz

_TYPE_TO_CH = {"en_uz": "E", "uz_en": "U", "def_word": "D"}
_CH_TO_TYPE = {v: k for k, v in _TYPE_TO_CH.items()}
_TYPE_ORDER = ["en_uz", "uz_en", "def_word"]
MAX_LEN = 64

_CODE_RE = re.compile(r"^b(\d+)u([\d_-]+)c(\d+)t(\d+)q([EUD]*)$")


def _compress(nums: list[int]) -> str:
    nums = sorted(set(nums))
    parts, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        parts.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return "_".join(parts)


def _expand(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split("_"):
        if "-" in part:
            lo, hi = part.split("-", 1)
            if lo.isdigit() and hi.isdigit():
                out.extend(range(int(lo), int(hi) + 1))
        elif part.isdigit():
            out.append(int(part))
    return sorted(set(out))


def encode_quiz(book: int, units: list[int], count: int, interval: int, types: list[str]) -> str:
    tc = "".join(_TYPE_TO_CH[t] for t in _TYPE_ORDER if t in (types or []))
    return f"b{book}u{_compress(units)}c{count}t{interval}q{tc}"


def decode_quiz(code: str) -> dict | None:
    """Parse a compact code → {book, units (numbers), count, interval, types}."""
    match = _CODE_RE.match(code or "")
    if match is None:
        return None
    units = _expand(match.group(2))
    if not units:
        return None
    return {
        "book": int(match.group(1)),
        "units": units,
        "count": int(match.group(3)),
        "interval": int(match.group(4)),
        "types": [_CH_TO_TYPE[c] for c in match.group(5)],
    }


def load_quiz(token: str) -> dict | None:
    """Resolve a share token (compact code or ``q<pk>``) to a runnable config.

    Returns {book_id, unit_ids, count, interval, types} or None if invalid.
    Compact codes carry book/unit *numbers*; they're resolved to ids here so a
    code stays valid even if unit rows are recreated.
    """
    token = (token or "").strip()
    if token[:1] == "q" and token[1:].isdigit():
        sq = SharedQuiz.objects.filter(pk=int(token[1:])).first()
        if sq is None:
            return None
        return {
            "book_id": sq.book_id,
            "unit_ids": list(sq.unit_ids),
            "count": sq.question_count,
            "interval": sq.interval_seconds,
            "types": list(sq.question_types),
        }
    dec = decode_quiz(token)
    if dec is None:
        return None
    book = Book.objects.filter(number=dec["book"]).first()
    if book is None:
        return None
    unit_ids = list(
        Unit.objects.filter(book=book, number__in=dec["units"]).values_list("id", flat=True)
    )
    if not unit_ids:
        return None
    return {
        "book_id": book.id,
        "unit_ids": unit_ids,
        "count": dec["count"],
        "interval": dec["interval"],
        "types": dec["types"],
    }


def card_for(token: str) -> dict | None:
    """Display fields for an inline share card, or None if the token is invalid."""
    dec = decode_quiz(token)
    if dec is None:
        return None
    book = Book.objects.filter(number=dec["book"]).first()
    if book is None:
        return None
    return {
        "book": book.title,
        "units": _compress(dec["units"]).replace("_", ", ").replace("-", "–"),
        "count": dec["count"],
        "interval": dec["interval"],
        "types": dec["types"],
    }
