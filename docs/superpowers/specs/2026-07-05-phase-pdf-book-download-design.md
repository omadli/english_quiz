# Faza PDF — Kitobni Yuklab Olish (Book PDF Download) — Dizayn Spec

**Sana:** 2026-07-05
**Faza:** PDF (kichik mustaqil ish; Faza 4d duel'dan alohida)
**Holat:** Tasdiqlash kutilmoqda (foydalanuvchi yo'q — standart qulflandi: "davom" → PDF)
**Tayanadi:** Faza 0-4c — tugallangan, `main`'da. (`Book`/`Unit`/`Word` modellari, `Book.pdf` FileField, Pillow card renderer, bot factory + conftest, `send_daily` tayyor.)

---

## 1. Maqsad va natija

Foydalanuvchi botда kitobni **PDF** sifatida yuklab oladi. `Book` modelida allaqachon `pdf` (FileField) bor — mo'ljallangan mexanizm shu. Agar kitobga PDF yuklangan bo'lsa, o'shani yuboradi; aks holda kitob so'zlaridan **Pillow ko'p-sahifali** lug'at PDF'ini generatsiya qiladi (yangi og'ir kutubxona shart emas — mavjud PIL card-renderer usuli).

Faza oxirida:
- `/book` → kitob (1-6) tanlash → PDF hujjat sifatida yuboriladi.
- `Book.pdf` mavjud → o'sha fayl; aks holda generatsiya qilingan lug'at PDF (so'zlar ro'yxati, ~22 qator/sahifa).
- Testlar o'tadi, `ruff` toza.

**Bu fazada YO'Q:** onlayn kitob o'qish (Faza 5, web); chiroyli tipografiya/reportlab (carryover); PDF cache (carryover).

---

## 2. Qarorlar

| Mavzu | Qaror |
|-------|-------|
| Manba | `Book.pdf` yuklangan bo'lsa — o'sha; aks holda PIL bilan generatsiya |
| Generatsiya | Pillow ko'p-sahifali PDF (`Image.save(..., "PDF", save_all=True, append_images=...)`), `ImageFont.load_default()` (mavjud card-renderer bilan izchil) |
| Daraja | Kitob-darajasi (`/book` → kitob tanla). Unit-darajasi kerak emas (butun kitob) |
| Sahifalash | ~22 qator/sahifa; har sahifada kitob sarlavhasi; so'zlar `unit, order` bo'yicha |
| Yuborish | `send_document(chat_id, data, filename)` (aiogram `send_document` + `BufferedInputFile`) |
| Yangi model | Yo'q — mavjud `Book`/`Unit`/`Word` |
| Yangi kutubxona | Yo'q — Pillow allaqachon bog'liqlik (Faza 2a) |
| Joy | Xizmat `apps/learning/services/book_pdf.py`; handler `bot/handlers/books.py` (yangi router) |

---

## 3. Ma'lumot manbai (yangi model yo'q)

- `Book`: `number`, `title`, `slug`, `pdf` (FileField, blank/null), `is_active`.
- `Unit`: `book` FK, `number`, ordering `(book, number)`.
- `Word`: `unit` FK, `en`, `uz`, `part_of_speech`, `order`; ordering `(unit, order)`. `Word.objects.filter(unit__book=book).select_related("unit").order_by("unit__number", "order")`.

---

## 4. Xizmatlar (`apps/learning/services/book_pdf.py`, yangi)

- `_render_page(title, rows) -> PIL.Image` — bitta sahifa: sarlavha + `rows` (`(index, "en — uz  POS")`) ; card-renderer bilan bir xil PIL usul (`Image.new`, `ImageDraw`, `load_default`).
- `build_book_vocab_pdf(book) -> bytes` — kitob so'zlarini `unit__number, order` bo'yicha oladi; ~22 tadan sahifalarga bo'ladi; `Image.save(buf, "PDF", save_all=True, append_images=[...])` bilan bytes qaytaradi. So'z yo'q bo'lsa — bitta bo'sh-ro'yxatli sahifa.
- `get_book_document(book_id) -> tuple[str, bytes] | None` — `Book.objects.get(pk=book_id)`; `book.pdf` bo'lsa `(f"{book.slug}.pdf", <fayl baytlari>)` (`with book.pdf.open("rb") as f: f.read()`); aks holda `(f"{book.slug}-lugat.pdf", build_book_vocab_pdf(book))`. Book topilmasa (yo'q) None (handler validatsiyasi uchun).
- `active_books() -> list[Book]` — `Book.objects.filter(is_active=True).order_by("number")`.

---

## 5. Bot handleri (`bot/handlers/books.py`, yangi router)

- `/book` → `active_books()` → inline ro'yxat (`pdf:book:<id>`) — "Qaysi kitobni yuklab olasiz?".
- `pdf:book:<id>` callback → `get_book_document(id)` (sync_to_async) → None bo'lsa "topilmadi"; aks holda `send_document(chat_id, data, filename)` (sync_to_async) + `callback.answer("Yuborilmoqda...")`. Katta generatsiya — best-effort; xatoda log + foydalanuvchiga "xatolik".
- Barcha ORM `sync_to_async` orqali.
- Router `bot/factory.py`'ga ulanadi (9-router) va `bot/tests/conftest.py` `_detach_handler_routers` ro'yxatiga `books` qo'shiladi.

## Sender (`bot/sender.py`)

- `send_document(chat_id, data: bytes, filename: str)` — sync wrapper (`_make_bot` → `bot.send_document(chat_id, BufferedInputFile(data, filename))` → close), mavjud `send_daily` naqshiga o'xshash.

---

## 6. Testlar (pytest + pytest-django)

- **`build_book_vocab_pdf`:** kitob + unit + so'zlar → PDF bytes (`%PDF` sarlavhasi bilan boshlanadi, bo'sh emas); so'zsiz kitob → hali ham valid PDF.
- **`get_book_document`:** `pdf` maydonsiz kitob → generatsiya qilingan `(-lugat.pdf, bytes)`; `pdf` maydonli kitob → yuklangan fayl `(slug.pdf, bytes)` (mock FileField); yo'q id → None.
- **`active_books`:** faol kitoblar `number` bo'yicha.
- **`/book` handler:** kitob ro'yxati yuboriladi (mock); `pdf:book:<id>` callback `send_document` chaqiradi (mock, mock get_book_document).
- **`send_document`:** `bot.send_document` `BufferedInputFile` bilan chaqiriladi (mock `_make_bot`).
- **Factory:** dispatcher `books` router'ini o'z ichiga oladi (≥9).
- Sender/tarmoq/PDF-yuborish mock. Test chiqishi toza.

---

## 7. Konfiguratsiya

- Yangi settings shart emas. (Xohlasa `PDF_ROWS_PER_PAGE` default 22.)

---

## 8. Muvaffaqiyat mezoni (Definition of Done)

- [ ] `apps/learning/services/book_pdf.py` — `build_book_vocab_pdf` + `get_book_document` + `active_books`.
- [ ] `send_document` (`bot/sender.py`).
- [ ] `/book` handler + `bot/handlers/books.py` router + keyboards + strings.
- [ ] Router `factory.py`'ga ulash + `conftest.py` detach ro'yxatiga qo'shish.
- [ ] Testlar yashil, `ruff` toza, docs.

---

## 9. Ochiq savollar / xavflar

- **Generatsiya og'irligi:** butun kitob (~600 so'z ≈ 27 sahifa PIL rendering) so'rov paytida generatsiya qilinadi — MVP uchun maqbul, lekin sekin bo'lishi mumkin. Cache (generatsiyani `Book.pdf`ga saqlash yoki Redis cache) → carryover.
- **Font sifati:** `load_default()` — oddiy bitmap font (card-renderer bilan izchil); chiroyli tipografiya (reportlab/TTF) → carryover. Uzbek `o'`/`g'` — mavjud card-renderer bilan bir xil cheklov.
- **`Book.pdf` mavjudligi:** hozircha yuklanmagan bo'lishi mumkin → generatsiya fallback shu sababli kerak (feature bo'sh qolmasin).
- **9-router:** `conftest.py` detach ro'yxati YANGILANISHI shart (aks holda to'liq suite ikkinchi `build_dispatcher()`da yiqiladi).
- **Katta fayl yuborish:** Telegram bot document limiti ~50MB — lug'at PDF undan kichik. Xavf yo'q.
