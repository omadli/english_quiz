import pytest

from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book, Unit, Word
from apps.learning.models import LearnedWord
from apps.learning.services.progress import mark_words_learned

pytestmark = pytest.mark.django_db


def _setup(tg_id=555):
    user = User.objects.create(first_name="Ali")
    TelegramAccount.objects.create(user=user, telegram_id=tg_id)
    book = Book.objects.create(number=1, title="B1", slug="b1")
    unit = Unit.objects.create(book=book, number=1)
    words = [
        Word.objects.create(unit=unit, en=f"w{i}", uz=f"u{i}", order=i) for i in range(3)
    ]
    return user, words


def test_mark_words_learned_creates_and_counts():
    user, words = _setup()
    ids = [w.id for w in words]
    assert mark_words_learned(555, ids) == 3
    assert set(LearnedWord.objects.filter(user=user).values_list("word_id", flat=True)) == set(ids)


def test_mark_words_learned_is_idempotent():
    user, words = _setup()
    ids = [w.id for w in words]
    mark_words_learned(555, ids)
    # re-taking the test marks nothing new and creates no duplicates
    assert mark_words_learned(555, ids) == 0
    assert LearnedWord.objects.filter(user=user).count() == 3


def test_mark_words_learned_unknown_user_noop():
    _, words = _setup(tg_id=555)
    assert mark_words_learned(999, [w.id for w in words]) == 0   # no account for 999
    assert mark_words_learned(555, []) == 0                       # empty list
