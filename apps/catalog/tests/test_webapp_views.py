import pytest
from django.urls import reverse

from apps.catalog.models import Book, Unit, Word

pytestmark = pytest.mark.django_db


def _seed():
    book = Book.objects.create(number=1, title="Book 1", slug="book-1", word_count=1)
    unit = Unit.objects.create(book=book, number=1, word_count=1)
    Word.objects.create(
        unit=unit, en="afraid", uz="qo'rqqan, cho'chigan", part_of_speech="adj.",
        definition="When someone is afraid, they feel fear.",
        example="The woman was afraid.", order=1,
    )
    return book, unit


def test_webapp_index_renders(client):
    resp = client.get(reverse("webapp"))
    assert resp.status_code == 200
    assert b"telegram-web-app.js" in resp.content


def test_api_books_lists_active_books(client):
    _seed()
    Book.objects.create(number=2, title="Hidden", slug="hidden", is_active=False)
    data = client.get(reverse("webapp_books")).json()
    assert [b["title"] for b in data["books"]] == ["Book 1"]


def test_api_units_lists_units_for_book(client):
    book, _ = _seed()
    data = client.get(reverse("webapp_units", args=[book.id])).json()
    assert data["units"][0]["number"] == 1


def test_api_words_returns_rich_payload(client):
    _, unit = _seed()
    w = client.get(reverse("webapp_words", args=[unit.id])).json()["words"][0]
    assert isinstance(w["id"], int)
    assert w["en"] == "afraid"
    assert w["uz"] == "qo'rqqan, cho'chigan"
    assert w["part_of_speech"] == "adj."
    assert w["definition"].startswith("When someone")
    assert w["example"] == "The woman was afraid."
    assert "image" in w


def test_api_search_matches_en_and_uz(client):
    _seed()
    assert len(client.get(reverse("webapp_search"), {"q": "afr"}).json()["words"]) == 1
    assert len(client.get(reverse("webapp_search"), {"q": "cho'ch"}).json()["words"]) == 1
    # results carry book/unit context
    hit = client.get(reverse("webapp_search"), {"q": "afraid"}).json()["words"][0]
    assert hit["book"] == 1 and hit["unit"] == 1


def test_api_search_ignores_short_queries(client):
    _seed()
    assert client.get(reverse("webapp_search"), {"q": "a"}).json()["words"] == []
