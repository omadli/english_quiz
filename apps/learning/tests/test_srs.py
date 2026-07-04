import datetime

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import WordProgress
from apps.learning.services.srs import apply_sm2, grade_answer

pytestmark = pytest.mark.django_db


def _progress():
    user = User.objects.create(first_name="T")
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    word = Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    return WordProgress.objects.create(user=user, word=word), user, word


def test_first_correct_sets_interval_1_learning():
    p, _, _ = _progress()
    apply_sm2(p, correct=True)
    assert p.repetitions == 1
    assert p.interval_days == 1
    assert p.status == WordProgress.Status.LEARNING
    assert p.correct_count == 1
    assert p.next_review == timezone.now().date() + datetime.timedelta(days=1)


def test_third_correct_marks_known_and_grows_interval():
    p, _, _ = _progress()
    apply_sm2(p, correct=True)   # rep1, interval 1
    apply_sm2(p, correct=True)   # rep2, interval 6
    apply_sm2(p, correct=True)   # rep3, interval round(6*ease)
    assert p.repetitions == 3
    assert p.status == WordProgress.Status.KNOWN
    assert p.interval_days > 6


def test_wrong_resets_repetitions_and_lowers_ease():
    p, _, _ = _progress()
    apply_sm2(p, correct=True)
    apply_sm2(p, correct=True)
    ease_before = p.ease_factor
    apply_sm2(p, correct=False)
    assert p.repetitions == 0
    assert p.interval_days == 1
    assert p.ease_factor == pytest.approx(max(1.3, ease_before - 0.2))
    assert p.wrong_count == 1


def test_ease_never_below_min():
    p, _, _ = _progress()
    for _ in range(10):
        apply_sm2(p, correct=False)
    assert p.ease_factor >= 1.3


def test_grade_answer_creates_progress():
    _, user, word = _progress()
    word2 = Word.objects.create(unit=word.unit, en="agree", uz="b", order=2)
    p = grade_answer(user, word2, correct=True)
    assert p.repetitions == 1
    assert WordProgress.objects.filter(user=user, word=word2).exists()
