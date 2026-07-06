from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render

from apps.catalog.models import Book, Unit, Word


def _word_payload(w: Word, with_context: bool = False) -> dict:
    data = {
        "en": w.en,
        "uz": w.uz,
        "part_of_speech": w.part_of_speech,
        "pronunciation": w.pronunciation,
        "definition": w.definition,
        "example": w.example,
        "image": w.image.url if w.image else None,
    }
    if with_context:
        data["book"] = w.unit.book.number
        data["unit"] = w.unit.number
    return data


def webapp_index(request):
    """The Telegram Mini App page (word browser). Data loads from the JSON
    endpoints below; the page itself is a self-contained template."""
    return render(request, "webapp/index.html")


def api_books(request):
    books = Book.objects.filter(is_active=True).order_by("number").values(
        "id", "number", "title", "word_count"
    )
    return JsonResponse({"books": list(books)})


def api_units(request, book_id: int):
    units = (
        Unit.objects.filter(book_id=book_id)
        .order_by("number")
        .values("id", "number", "title", "word_count")
    )
    return JsonResponse({"units": list(units)})


def api_words(request, unit_id: int):
    words = Word.objects.filter(unit_id=unit_id).select_related("unit").order_by("order")
    return JsonResponse({"words": [_word_payload(w) for w in words]})


def api_search(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"words": []})
    words = (
        Word.objects.filter(Q(en__icontains=query) | Q(uz__icontains=query))
        .select_related("unit", "unit__book")
        .order_by("en")[:50]
    )
    return JsonResponse({"words": [_word_payload(w, with_context=True) for w in words]})
