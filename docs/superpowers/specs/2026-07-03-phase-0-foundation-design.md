# Faza 0 — Poydevor (Foundation) — Dizayn Spec

**Sana:** 2026-07-03
**Faza:** 0 / 6 (`product-vision-and-roadmap.md` ga qarang)
**Holat:** Tasdiqlash kutilmoqda

---

## 1. Maqsad va natija

Loyihaning texnik poydevorini zamonaviylashtirish va mustahkam ma'lumot/media asosini yaratish. Faza oxirida:

- `docker compose up` — barcha xizmatlar (db, redis, web, worker, beat) ishga tushadi.
- `manage.py migrate && manage.py import_words --with-audio` — 6 kitob, ~180 unit, ~4000 so'z (rasm + native audio bilan) bazaga yuklanadi.
- **django-unfold admin** — Book → Unit → Word ierarxiyasi ko'rinadi, qidiriladi, rasm/audio preview bilan.
- Testlar o'tadi, `ruff` toza.

**Bu fazada YO'Q:** bot handlerlari, onboarding, jadval mantig'i, o'quv/SRS, imtihon, guruh quiz, rollar/guardianship, web sahifalar, o'yinlar. (Bularning modellari o'z fazalarida qo'shiladi — Faza 0'ni ortiqcha shishirmaymiz.)

---

## 2. Texnologiya to'plami (aniq versiyalar)

| Qatlam | Tanlov | Izoh |
|--------|--------|------|
| Til | Python 3.12 | |
| Framework | Django 5.2 LTS | Uzoq muddat qo'llab-quvvatlanadi; unfold/celery ekotizimi mos |
| Dep manager | **uv** + `pyproject.toml` + `uv.lock` | Tez, zamonaviy |
| DB | PostgreSQL 16 | |
| Cache/broker/FSM | Redis 7 | Celery broker+result, keyingi fazalarda bot FSM va cache |
| Vazifalar | Celery 5 + Celery Beat | |
| Admin | **django-unfold** | Zamonaviy admin UI |
| Config | `django-environ` (env asosida) | 12-factor |
| Rasm | Pillow | |
| Audio | Native mp3 import + `gTTS` fallback (pluggable TTS) | |
| Bot (kelajak) | aiogram 3.x | Faza 0'da faqat e'lon qilinadi, stub |
| Test | pytest + pytest-django + factory_boy | |
| Lint/format | ruff + ruff format + pre-commit | |
| Konteyner | Docker + docker compose | |
| Static (prod) | whitenoise | |

---

## 3. Repo strukturasi

```
english_quiz/
├── config/                      # src/ dan qayta nomlanadi
│   ├── settings/
│   │   ├── base.py              # umumiy sozlamalar (env'dan)
│   │   ├── dev.py               # DEBUG=True, lokal
│   │   └── prod.py              # DEBUG=False, whitenoise, xavfsizlik
│   ├── celery.py                # Celery app
│   ├── urls.py · asgi.py · wsgi.py
├── apps/
│   ├── common/                  # TimeStampedModel, TTS abstraksiyasi, utillar
│   ├── catalog/                 # Book, Unit, Word + importer + admin
│   └── accounts/                # User (telefon ixtiyoriy) + TelegramAccount
├── bot/                         # aiogram skeleti (Faza 1 — hozir bo'sh stub)
├── data/                        # book1-6.json fixture'lar (mavjud)
├── media/                       # uploads/ dan qayta nomlanadi (rasm/audio)
│   ├── images/words/{book}/{unit}/{en}.jpg
│   └── audio/words/{book}/{unit}/{en}.mp3
├── tests/
├── docs/
├── compose.yaml · Dockerfile · .dockerignore
├── pyproject.toml · uv.lock · .env.example
├── manage.py · Readme.md
```

**App label eslatmasi:** `words` → `apps.catalog` ga ko'chadi. Eski `loaddata`'ga tayanmaymiz (sxema qayta dizayn qilingani uchun) — o'rniga **maxsus importer** eski JSONni o'qib Book/Unit/Word quradi. Shu sabab app nomini o'zgartirish xavfsiz.

---

## 4. Ma'lumot modellari (Faza 0 — faqat kontent)

### `apps/common/models.py`
- **`TimeStampedModel`** (abstract): `created_at`, `updated_at`.

### `apps/catalog/models.py`

**`Book(TimeStampedModel)`**
| Maydon | Tur | Izoh |
|--------|-----|------|
| `number` | PositiveSmallInt, unique (1–6) | Kitob raqami |
| `title` | Char | "4000 Essential English Words 1" |
| `slug` | Slug, unique | |
| `description` | Text, blank | |
| `level` | Char, choices (A1…C1), blank | CEFR daraja |
| `cover` | Image, blank | Muqova |
| `pdf` | File, blank | Yuklab olish / onlayn o'qish (Faza 5) |
| `word_count` | PositiveInt, default 0 | Import'da yangilanadi |
| `is_active` | Bool, default True | |

**`Unit(TimeStampedModel)`**
| Maydon | Tur | Izoh |
|--------|-----|------|
| `book` | FK→Book, related_name="units" | |
| `number` | PositiveSmallInt | Unit raqami |
| `title` | Char, blank | "Unit 1" |
| `slug` | Slug | |
| `word_count` | PositiveInt, default 0 | |
- `UniqueConstraint(book, number)`; `ordering = (book, number)`.

**`Word(TimeStampedModel)`**
| Maydon | Tur | Izoh |
|--------|-----|------|
| `unit` | FK→Unit, related_name="words" | |
| `order` | PositiveSmallInt | Unit ichidagi tartib |
| `en` | Char(100) | Inglizcha |
| `uz` | Char(255) | O'zbekcha (lokal fixture'dan) |
| `part_of_speech` | Char(20), blank | `pronunciation` oxiridan parslanadi (adj./v./n.) |
| `pronunciation` | Char(100), blank | IPA, masalan `[əˈfreid]` |
| `definition` | Text, blank | |
| `example` | Text, blank | HTML `<strong>` bilan |
| `image` | Image, blank | `images/words/{book}/{unit}/{en}.jpg` |
| `audio_en` | File, blank | Native mp3 (yoki gTTS fallback) |
| `audio_uz` | File, blank | Ixtiyoriy (pluggable TTS) |
- `UniqueConstraint(unit, en)`; `ordering = (unit, order)`; `en` bo'yicha index (qidiruv).
- `@property book` → `self.unit.book`.

> **Ko'chiriladi:** hozirgi `Word.book`/`Word.unit` (int) → `Book`/`Unit` FK. `speach()` util `apps/common/tts.py` ga ko'chadi.

> **Kechiktiriladi (o'z fazasida):** `Exercise`, `Reading` (masofaviy data'da bor, web/Faza 5 uchun). Importer ularni hozir o'qimaydi.

### `apps/accounts/models.py`
- **`User`** (mavjud custom modeldan): `phone_number` → **null=True, blank=True** (unique, null'lar takrorlanishi mumkin). Manager'ga `create_user` telefonsiz ishlashiga yo'l — telegram user uchun alohida yo'l keyingi fazada. `USERNAME_FIELD='phone_number'` (superuser uchun) saqlanadi.
- **`TelegramAccount(TimeStampedModel)`**: `user` OneToOne→User, `telegram_id` BigInt unique, `username`, `first_name`, `last_name`, `language_code`, `is_premium` bool, `blocked_bot` bool default False.

> **Kechiktiriladi:** rollar (parent/teacher), guardianship, referal — Faza 4. Faza 0 faqat sxemani telegram-first bo'lishga tayyorlaydi.

---

## 5. Import pipeline

### `apps/catalog/management/commands/import_words.py`
- **Kirish:** lokal `data/book{n}.json` (dumpdata format: `fields`: book, unit, en, uz, definition, example, pronunciation, image).
- **Mantiq:** har yozuv uchun `Book` (title mapping: "4000 Essential English Words N"), `Unit` (book+unit raqami), `Word` (`update_or_create` by `(unit, en)`) yaratadi. `part_of_speech` ni `pronunciation` oxiridan regex bilan ajratadi (`\]\s*(.+)$` → "adj."/"v."/"n."). Mavjud rasm faylini (`images/words/{book}/{unit}/{en}.jpg`) `image` ga bog'laydi.
- **Idempotent:** qayta ishga tushsa yangilaydi, dublikat yaratmaydi. Oxirida `Book.word_count`, `Unit.word_count` yangilanadi.
- **Flaglar:** `--book N` (bitta kitob), `--dry-run`, `--with-audio`.

### Audio import (`--with-audio` yoki alohida `import_audio` buyrug'i)
- Masofaviy `essentialenglish.review/apps-data/4000-essential-english-words-{book}/data/data.json` ni yuklaydi.
- Har unit ichida so'zni `en` (case-insensitive) bo'yicha moslashtiradi → `sound` (mp3 nomi) → to'liq URL quradi → `media/audio/words/{book}/{unit}/{en}.mp3` ga yuklab, `Word.audio_en` ga yozadi.
- **Fallback:** masofaviy audio topilmasa, `gTTS` bilan generatsiya qiladi.
- Tarmoq xatolari: retry + skip + log; import umuman to'xtamaydi.

### `apps/common/tts.py` — pluggable TTS
- `TTSProvider` interfeysi: `synthesize(text: str, lang: str) -> bytes`.
- `GTTSProvider` (default, ingliz `co.uk`). Kelajakda `GoogleCloudTTSProvider`, `ElevenLabsProvider` — sozlama orqali almashtiriladi (`settings.TTS_PROVIDER`).

---

## 6. Konfiguratsiya (settings)

- `base/dev/prod` bo'linadi; barcha maxfiy qiymatlar env'dan (`django-environ`): `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `TTS_PROVIDER`, `BOT_TOKEN` (Faza 1).
- `DATABASES` → Postgres; `CACHES` → Redis.
- `TIME_ZONE='Asia/Tashkent'`, `USE_TZ=True`.
- i18n: `LANGUAGE_CODE='uz'`, `LANGUAGES=[uz, en]`, `LocaleMiddleware`, `locale/` papka. (To'liq tarjima keyin; hozir infrastruktura.)
- **UNFOLD** config: sayt sarlavhasi, rang sxemasi (ko'k/teal), Book/Unit/Word/User ro'yxatlari.
- Static: dev — Django; prod — whitenoise. Media: dev — Django; prod — nginx/volume.

---

## 7. Celery

- `config/celery.py`: app, `autodiscover_tasks()`, Redis broker/result.
- Namunaviy `ping` task + Beat'da namunaviy jadval — worker+beat simligini tekshirish uchun. Haqiqiy jadvalli vazifalar (ertalabki so'z, kechki imtihon) keyingi fazalarda.

---

## 8. Docker

**`Dockerfile`:** `python:3.12-slim`, `uv` bilan deps, kod nusxasi, entrypoint (migrate + collectstatic + run).

**`compose.yaml` xizmatlari:**
| Xizmat | Image/manba | Rol |
|--------|-------------|-----|
| `db` | postgres:16 | Ma'lumot bazasi (volume) |
| `redis` | redis:7 | Broker/result/cache |
| `web` | build | Django (gunicorn/uvicorn) |
| `worker` | build | Celery worker |
| `beat` | build | Celery beat |
| `bot` | build | aiogram (Faza 1 — hozir izohli/stub) |

`.env` orqali config; `media/` va `db` uchun volume'lar.

---

## 9. Testlar (pytest)

- Model yaratish (Book/Unit/Word, constraint'lar).
- Importer idempotentligi (kichik namunaviy JSON fixture bilan).
- `part_of_speech` parslash mantig'i.
- TTS interfeys (GTTSProvider mock).
- Settings yuklanishi (dev).

Maqsad: asosiy mantiqni qamrab olish, 100% emas.

---

## 10. Mavjud loyihadan o'tish rejasi

1. `src/` → `config/`; settings `base/dev/prod` ga bo'linadi.
2. `words/` → `apps/catalog/`, `accounts/` → `apps/accounts/`; app label'lar, importlar, `AUTH_USER_MODEL='accounts.User'` yangilanadi.
3. Eski migratsiyalar o'chiriladi, yangi initial migratsiya yaratiladi (sxema qayta dizayn, prod data yo'q).
4. `uploads/` → `media/` (`git mv`; ichki `images/words/...` struktura saqlanadi, shuning uchun `image` yo'llari buzilmaydi).
5. Ma'lumot `loaddata` emas, **`import_words`** orqali keladi.
6. `requirements.txt` → `pyproject.toml` (uv).

---

## 11. Muvaffaqiyat mezoni (Definition of Done)

- [ ] `docker compose up` — db, redis, web, worker, beat ishlaydi.
- [ ] `migrate` + `import_words --with-audio` — 6 kitob / ~180 unit / ~4000 so'z, rasm + audio bilan.
- [ ] Unfold admin: Book→Unit→Word browse/search/filter, rasm+audio preview.
- [ ] `pytest` yashil, `ruff check` toza.
- [ ] `.env.example`, yangilangan `Readme.md` (o'rnatish qadamlari).

---

## 12. Ochiq savollar / xavflar

- **Masofaviy audio URL namunasi** import paytida tasdiqlanadi (`sound` → mp3 to'liq yo'li). Agar tuzilma boshqacha bo'lsa, importer moslashtiriladi; gTTS fallback kafolat beradi.
- **Django 5.2 vs 6.x:** LTS (5.2) barqarorlik uchun tanlandi; kerak bo'lsa keyin yangilanadi.
- **Web login (6 xonali kod) va rollar** — Faza 1/4/5, lekin User sxemasi hozir tayyorlanadi.
