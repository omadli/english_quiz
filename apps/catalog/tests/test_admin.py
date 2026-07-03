import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.catalog.models import Book, Unit, Word

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    user = User.objects.create(
        first_name="Admin", phone_number=998900000000, is_staff=True, is_superuser=True
    )
    user.set_password("pw")
    user.save()
    client.force_login(user)
    return client


def test_word_changelist_loads(admin_client):
    book = Book.objects.create(number=1, title="Book 1", slug="book-1")
    unit = Unit.objects.create(book=book, number=1)
    Word.objects.create(unit=unit, en="afraid", uz="a", order=1)
    resp = admin_client.get(reverse("admin:catalog_word_changelist"))
    assert resp.status_code == 200
    assert b"afraid" in resp.content
