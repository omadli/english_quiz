import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import DailySession, SessionWord, WordProgress
from apps.learning.services.exam import build_questions, select_exam_words

pytestmark = pytest.mark.django_db


@pytest.fixture
def book_words():
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    words = [
        Word.objects.create(unit=unit, en=f"w{i}", uz=f"uz{i}", definition=f"def {i}",
                            part_of_speech="n.", order=i)
        for i in range(1, 7)
    ]
    return book, unit, words


def test_build_questions_round_robin_types(book_words):
    _, _, words = book_words
    qs = build_questions(words[:3])
    assert [q["question_type"] for q in qs] == ["en_uz", "uz_en", "def_word"]


def test_build_questions_options_have_correct_and_are_distinct(book_words):
    _, _, words = book_words
    qs = build_questions(words[:4])
    for q in qs:
        assert len(q["options"]) == 4
        assert len(set(q["options"])) == 4  # distinct
        assert q["options"][q["correct_option"]] is not None
        # correct value is at the correct_option index
        assert 0 <= q["correct_option"] < 4


def test_en_uz_correct_option_is_the_uz_translation(book_words):
    _, _, words = book_words
    q = build_questions([words[0]])[0]  # index 0 → en_uz
    assert q["question_type"] == "en_uz"
    assert q["options"][q["correct_option"]] == words[0].uz


def test_select_exam_words_includes_day_and_due_reviews(book_words):
    _, unit, words = book_words
    user = User.objects.create(first_name="T")
    session = DailySession.objects.create(user=user, date=timezone.now().date())
    # day words: w1, w2
    for i, w in enumerate(words[:2], start=1):
        SessionWord.objects.create(daily_session=session, word=w, order=i)
    # a due review word: w5 (learning, next_review yesterday)
    WordProgress.objects.create(
        user=user, word=words[4], status=WordProgress.Status.LEARNING,
        next_review=timezone.now().date() - datetime.timedelta(days=1),
    )
    # a not-due word: w6 (next_review tomorrow) — excluded
    WordProgress.objects.create(
        user=user, word=words[5], status=WordProgress.Status.LEARNING,
        next_review=timezone.now().date() + datetime.timedelta(days=1),
    )
    result = select_exam_words(session, review_cap=10)
    ens = [w.en for w in result]
    assert "w1" in ens and "w2" in ens   # day words
    assert "w5" in ens                    # due review
    assert "w6" not in ens                # not due
    assert len(ens) == len(set(ens))      # deduped
