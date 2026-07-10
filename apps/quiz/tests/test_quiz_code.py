import re

import pytest

from apps.catalog.models import Book, Unit
from apps.quiz.models import SharedQuiz
from apps.quiz.services.quiz_code import (
    MAX_LEN,
    card_for,
    decode_quiz,
    encode_quiz,
    load_quiz,
)

_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")  # Telegram deep-link start-param charset


def test_encode_is_deep_link_safe_and_short():
    code = encode_quiz(4, [1, 2, 3, 4], 10, 30, ["en_uz", "uz_en", "def_word"])
    assert code == "b4u1-4c10t30qEUD"
    assert _SAFE.match(code)
    assert len(code) <= MAX_LEN


def test_encode_compresses_ranges_and_lists():
    assert encode_quiz(1, [1, 2, 3, 7, 8], 5, 20, ["en_uz"]) == "b1u1-3_7-8c5t20qE"
    assert encode_quiz(2, [1, 3, 5], 5, 20, ["uz_en"]) == "b2u1_3_5c5t20qU"


def test_round_trip():
    dec = decode_quiz("b4u1-3_7-8c15t45qED")
    assert dec == {
        "book": 4,
        "units": [1, 2, 3, 7, 8],
        "count": 15,
        "interval": 45,
        "types": ["en_uz", "def_word"],
    }


def test_decode_rejects_garbage():
    for bad in ["", "hello", "quiz_5", "b4c10t30qE", "b4u_c10t30qE"]:
        assert decode_quiz(bad) is None


def test_all_units_stays_tiny():
    code = encode_quiz(6, list(range(1, 31)), 30, 60, ["en_uz", "uz_en", "def_word"])
    assert code == "b6u1-30c30t60qEUD"  # 30 units → one range
    assert len(code) <= MAX_LEN


@pytest.mark.django_db
def test_load_quiz_compact_resolves_unit_ids():
    book = Book.objects.create(number=4, title="B4", slug="b4")
    u1 = Unit.objects.create(book=book, number=1)
    u2 = Unit.objects.create(book=book, number=2)
    Unit.objects.create(book=book, number=5)  # not selected
    cfg = load_quiz("b4u1-2c10t30qE")
    assert cfg["book_id"] == book.id
    assert sorted(cfg["unit_ids"]) == sorted([u1.id, u2.id])
    assert cfg["count"] == 10 and cfg["interval"] == 30 and cfg["types"] == ["en_uz"]


@pytest.mark.django_db
def test_load_quiz_unknown_book_or_units_returns_none():
    assert load_quiz("b9u1c10t30qE") is None                 # no such book
    Book.objects.create(number=4, title="B4", slug="b4")     # book exists, unit doesn't
    assert load_quiz("b4u99c10t30qE") is None


@pytest.mark.django_db
def test_load_quiz_db_fallback_token():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    sq = SharedQuiz.objects.create(
        created_by_telegram_id=1, book=book, unit_ids=[7, 8],
        question_count=12, interval_seconds=25, question_types=["uz_en"],
    )
    cfg = load_quiz(f"q{sq.id}")
    assert cfg == {
        "book_id": book.id, "unit_ids": [7, 8],
        "count": 12, "interval": 25, "types": ["uz_en"],
    }


@pytest.mark.django_db
def test_card_for_renders_display_fields():
    Book.objects.create(number=4, title="4000 Words 4", slug="b4")
    card = card_for("b4u1-3_7c10t30qEU")
    assert card["book"] == "4000 Words 4"
    assert card["units"] == "1–3, 7"
    assert card["count"] == 10
    assert card_for("garbage") is None
