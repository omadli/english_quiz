from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalog.models import Book
from apps.catalog.tests.test_webapp_profile import TOKEN, _init_data, _user

pytestmark = pytest.mark.django_db

URL = "/webapp/api/send-pdf/{}/"
AUTH = {"HTTP_X_TELEGRAM_INIT_DATA": _init_data({"id": 555, "first_name": "Ali"})}


def _book(number: int = 1, file_id: str = "", is_active: bool = True) -> Book:
    return Book.objects.create(
        number=number,
        title=f"Book {number}",
        is_active=is_active,
        telegram_file_id=file_id,
        pdf=SimpleUploadedFile(f"b{number}.pdf", b"%PDF-1.4 fake", content_type="application/pdf"),
    )


def test_send_pdf_requires_init_data(client, settings):
    settings.BOT_TOKEN = TOKEN
    book = _book()
    assert client.post(URL.format(book.id)).status_code == 401


def test_send_pdf_uploads_bytes_then_caches_file_id(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user(555)
    book = _book()
    with patch("bot.sender.send_document", return_value="FILEID-1") as send:
        resp = client.post(URL.format(book.id), **AUTH)
    assert resp.status_code == 200 and resp.json() == {"ok": True}
    chat_id, payload, _filename = send.call_args.args
    assert chat_id == 555
    assert isinstance(payload, bytes)  # no cache yet → upload the real bytes
    book.refresh_from_db()
    assert book.telegram_file_id == "FILEID-1"


def test_send_pdf_reuses_cached_file_id(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user(555)
    book = _book(file_id="FILEID-CACHED")
    with patch("bot.sender.send_document", return_value="FILEID-CACHED") as send:
        assert client.post(URL.format(book.id), **AUTH).status_code == 200
    _chat_id, payload, _filename = send.call_args.args
    assert payload == "FILEID-CACHED"  # sent by id — never re-uploaded


def test_send_pdf_rejects_get(client, settings):
    settings.BOT_TOKEN = TOKEN  # a DM is a side effect; GET must not trigger one
    _user(555)
    book = _book()
    with patch("bot.sender.send_document") as send:
        assert client.get(URL.format(book.id), **AUTH).status_code == 405
    send.assert_not_called()


def test_send_pdf_rejects_inactive_book(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user(555)
    book = _book(is_active=False)
    assert client.post(URL.format(book.id), **AUTH).status_code == 404


def test_send_pdf_reports_send_failure(client, settings):
    settings.BOT_TOKEN = TOKEN
    _user(555)
    book = _book()
    with patch("bot.sender.send_document", side_effect=RuntimeError("blocked")):
        resp = client.post(URL.format(book.id), **AUTH)
    assert resp.status_code == 502 and resp.json() == {"ok": False}
    book.refresh_from_db()
    assert book.telegram_file_id == ""  # a failed send must not poison the cache
