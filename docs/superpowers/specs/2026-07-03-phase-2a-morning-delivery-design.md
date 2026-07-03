# Faza 2a — Ertalabki yetkazish (Morning Delivery) — Dizayn Spec

**Sana:** 2026-07-03
**Faza:** 2a (2/6 fazaning birinchi yarmi; `product-vision-and-roadmap.md` ga qarang)
**Holat:** Tasdiqlash kutilmoqda
**Tayanadi:** Faza 0 (poydevor) + Faza 1 (bot yadrosi) — tugallangan, `main`'da.

---

## 1. Maqsad va natija

Har foydalanuvchiga o'zi sozlagan vaqtda (`morning_time`, `study_weekdays`, timezone bo'yicha) kunlik yangi so'zlar to'plamini avtomatik yetkazish: **kunlik jadval-karta rasmi** + har so'z alohida (tarjima, rasm, **birlashtirilgan audio**: native inglizcha talaffuz + o'zbekcha, `audio_repeat` marta). Pozitsiya oldinga siljiydi va kun `DailySession`'da qayd etiladi.

Faza oxirida:
- Celery Beat har daqiqada due-check qiladi; vaqti kelgan foydalanuvchilarga yetkazish taski navbatga qo'yiladi.
- Yetkazish: keyingi `words_per_session` so'z tanlanadi, pozitsiya siljiydi, karta+audio generatsiya qilinadi, bot orqali yuboriladi.
- `DailySession` + har so'z uchun `WordProgress` (status=new) yoziladi.
- Testlar o'tadi, `ruff` toza.

**Bu fazada YO'Q (Faza 2b):** kechki imtihon, quiz-poll baholash, SM-2 yangilash mantig'i, kunlik hisobot. (`WordProgress` modeli va SM-2 maydonlari shu yerda yaratiladi; ularni yangilash mantig'i 2b'da.)

---

## 2. Qarorlar

| Mavzu | Qaror |
|-------|-------|
| Jadval mexanizmi | **Celery Beat** har 60s `dispatch_morning_deliveries` taskini ishga tushiradi; u timezone bo'yicha due foydalanuvchilarni topib per-user yetkazish taskini navbatga qo'yadi (Faza 0 spec'idagi yondashuv) |
| Yetkazish formati | Kunlik **jadval-karta** (Pillow) + har so'z alohida (tarjima+rasm+audio) |
| Audio | Native inglizcha mp3 (`Word.audio_en`) + o'zbekcha (gTTS) birlashtirilib, `audio_repeat` marta. Birlashtirish: **pydub + ffmpeg** |
| Chiquvchi yuborish | `bot/sender.py` — sync wrapper (aiogram Bot'ni `asyncio.run` bilan) Celery taskidan chaqiriladi. Kiruvchi yangilanishlar aiogram polling'da (Faza 1) qoladi |
| Idempotentlik | `DailySession(user, date)` `get_or_create` bilan bir kunда bir marta yetkaziladi |
| Bloklangan user | `TelegramForbiddenError` → `TelegramAccount.blocked_bot=True`, o'tkazib yuboriladi |

---

## 3. Ma'lumot modellari (`apps/learning`'ga qo'shiladi)

### `DailySession(TimeStampedModel)`
| Maydon | Tur | Izoh |
|--------|-----|------|
| `user` | FK→User, related_name="daily_sessions" | |
| `date` | DateField | Foydalanuvchi timezone'idagi sana |
| `book` / `unit` | FK→catalog.Book / Unit, null | Boshlang'ich pozitsiya |
| `status` | Char choices: `pending`/`delivered`/`exam_sent`/`completed` | `exam_sent`/`completed` 2b'da ishlatiladi |
| `delivered_at` | DateTime null | |
| `exam_sent_at` / `completed_at` | DateTime null | 2b uchun |
| `score` / `total` | PositiveSmallInt null | 2b uchun |
- `UniqueConstraint(user, date)`; `ordering=("-date",)`.

### `SessionWord` (through)
- `daily_session` FK (related_name="session_words"), `word` FK→catalog.Word, `order` PositiveSmallInt.
- `DailySession.words = M2M(Word, through=SessionWord)`.

### `WordProgress(TimeStampedModel)` — SM-2 SRS holati (2a yaratadi, 2b yangilaydi)
| Maydon | Tur | Standart | Izoh |
|--------|-----|----------|------|
| `user` | FK→User, related_name="word_progress" | | |
| `word` | FK→catalog.Word | | |
| `status` | Char choices: `new`/`learning`/`known` | `new` | |
| `repetitions` | PositiveSmallInt | 0 | SM-2 |
| `ease_factor` | Float | 2.5 | SM-2 |
| `interval_days` | PositiveSmallInt | 0 | SM-2 |
| `next_review` | DateField null | | SM-2 |
| `correct_count` / `wrong_count` | PositiveSmallInt | 0 | |
| `last_reviewed` | DateTime null | | |
| `first_seen` | DateTime (auto) | | Yetkazilgan vaqt |
- `UniqueConstraint(user, word)`.

unfold admin: `DailySession`, `WordProgress`.

---

## 4. Jadval dvigateli (`apps/learning/tasks.py` + Celery Beat)

- **`dispatch_morning_deliveries()`** (Celery task, Beat har 60s): faol+onboarded profillar bo'yicha yuradi; har biriga `now`ni profil timezone'ida hisoblaydi; agar `local.weekday() ∈ study_weekdays` va `local` vaqti `morning_time` daqiqasiga to'g'ri kelsa va shu local sana uchun `DailySession` hali yo'q bo'lsa → `deliver_daily_words.delay(user_id)`. Dublikat dispatch'dan `DailySession(user, date)` `get_or_create` (pending) himoya qiladi.
- **`deliver_daily_words(user_id)`** (Celery task): quyida (5-bo'lim).
- **Beat ro'yxatga olish:** `python manage.py setup_periodic_tasks` — idempotent buyruq (`django_celery_beat` `IntervalSchedule(60s)` + `PeriodicTask('dispatch_morning_deliveries')` `update_or_create`). Readme'ga qo'shiladi (migrate'dan keyin bir marta).
- Due-check mantig'i alohida testlanadigan funksiya: `is_due_for_delivery(profile, now_utc) -> bool`.

---

## 5. Yetkazish oqimi (`deliver_daily_words`)

1. Profil + telegram_id yuklanadi; `blocked_bot` yoki `is_active=False` bo'lsa skip.
2. `DailySession(user, local_date)` `get_or_create` — allaqachon `delivered` bo'lsa skip (idempotent).
3. **`select_next_words(profile)`** — joriy pozitsiyadan (`current_book/unit/word_order`) keyingi `words_per_session` so'z, unit/kitob chegaralaridan o'tib. Pozitsiyani oxirgi so'zdan keyinga siljitadi. Kontent tugasa: to'xtatadi (yoki qayta boshlaydi — sozlanadi; standart: to'xtatadi + xabar).
4. `SessionWord` + `WordProgress(status=new)` yozuvlari yaratiladi.
5. **Karta:** `render_daily_card(words, date)` (Pillow) → jadval rasmi (EN | UZ | POS, sarlavhada sana/unit) → botga `sendPhoto`.
6. Har so'z uchun: matn (EN, POS, talaffuz, UZ, definition, misol) + rasm (`word.image`) + **birlashtirilgan audio** (`build_word_audio`).
7. `DailySession.status=delivered`, `delivered_at=now`.

### Media generatsiyasi (`apps/learning/services/`)
- **`cards.py: render_daily_card(words, date) -> bytes`** — Pillow PNG, so'zlar jadvali.
- **`audio.py: build_word_audio(word, repeat) -> bytes`** — `word.audio_en` (native mp3) + gTTS(`word.uz`, lang="uz") ni pydub bilan birlashtiradi, `repeat` marta. **Kesh:** `media/audio/combined/{book}/{unit}/{en}_r{repeat}.mp3` — mavjud bo'lsa qayta ishlatadi. Native mp3 yo'q bo'lsa gTTS fallback (Faza 0 TTS abstraksiyasi).

### Yuborish (`bot/sender.py`)
- Sync funksiyalar (`send_photo`, `send_message`, `send_audio`) aiogram `Bot`'ni `asyncio.run` bilan o'raydi (Celery sync taskidan chaqiriladi). Token `settings.BOT_TOKEN`'dan.
- `TelegramForbiddenError` → `blocked_bot=True`.

---

## 6. So'z tanlash va pozitsiya (`apps/learning/services/delivery.py`)

- `select_next_words(profile) -> list[Word]` — so'zlar `(book.number, unit.number, word.order)` tartibida; joriy pozitsiyadan keyingi N ta. Pozitsiya `current_book/current_unit/current_word_order` bilan aniqlanadi.
- Pozitsiyani siljitish: oxirgi yetkazilgan so'zdan keyingi holatga. Kitob/unit chegarasidan avtomatik o'tadi.
- Kontent tugasa: bo'sh ro'yxat qaytaradi; `deliver_daily_words` "tabriklaymiz, kurs tugadi" xabarini yuboradi va pozitsiyani o'zgartirmaydi.

---

## 7. Testlar (pytest + pytest-django)

- **Due-check:** `is_due_for_delivery` — weekday, vaqt mosligi, timezone (turli tz), allaqachon yetkazilgan holat. Toza unit testlar.
- **`select_next_words`:** batch tanlash + pozitsiya siljish, unit/kitob chegarasi, kontent oxiri. `django_db`.
- **Karta:** `render_daily_card` bo'sh bo'lmagan PNG bayt qaytaradi (smoke).
- **Audio:** `build_word_audio` — gTTS + audio_en mock, kesh qayta ishlatilishi.
- **`deliver_daily_words`:** mock'langan sender bilan integratsiya — `DailySession` + `WordProgress` yaratadi, pozitsiya siljiydi, sender chaqiriladi, idempotent (ikki marta chaqirilsa dublikat yo'q). `django_db` + mock.
- **`dispatch_morning_deliveries`:** `deliver_daily_words` mock — faqat due userlar uchun `.delay` chaqiriladi.
- Sender/media testlari tarmoq/ffmpeg'ga tegmaydi (mock). Test chiqishi toza.

---

## 8. Konfiguratsiya va Docker

- **ffmpeg** — `Dockerfile`'ga `apt-get install ffmpeg` qo'shiladi (pydub uchun). `pydub` `pyproject`'ga qo'shiladi. Lokal dev uchun ffmpeg kerak (yoki audio taskini Docker'da ishga tushirish) — Readme'da eslatiladi.
- Celery worker + beat allaqachon compose'da (Faza 0). `setup_periodic_tasks` migrate'dan keyin ishga tushiriladi.
- `BOT_TOKEN` yuborish uchun kerak (Faza 1'dagidek).

---

## 9. Muvaffaqiyat mezoni (Definition of Done)

- [ ] `DailySession`/`SessionWord`/`WordProgress` modellari + migratsiya + unfold admin.
- [ ] `is_due_for_delivery` + `dispatch_morning_deliveries` + Beat ro'yxatga olish (`setup_periodic_tasks`).
- [ ] `select_next_words` (pozitsiya siljish, chegaralar), `render_daily_card`, `build_word_audio` (kesh), `bot/sender.py`.
- [ ] `deliver_daily_words` — uchidan-uchiga (mock sender) yetkazadi, idempotent.
- [ ] Testlar yashil, `ruff` toza. `.env`/Readme yangilanadi.

---

## 10. Ochiq savollar / xavflar

- **ffmpeg bog'liqligi:** pydub audio birlashtirish uchun ffmpeg talab qiladi; Docker image'ga qo'shiladi. Agar og'ir bo'lsa, muqobil: sodda MP3 byte-concat yoki EN/UZ alohida audio xabarlar (kelgusi refinement). Standart: pydub+ffmpeg.
- **Real yuborish tekshiruvi** BotFather token'ini talab qiladi (Faza 1'dagidek); usiz kod/testlar mock bilan to'liq tekshiriladi.
- **Audio generatsiya yuki:** kesh (per word+repeat) qayta hisoblashni kamaytiradi. Ko'p foydalanuvchi bo'lsa keyin optimizatsiya.
- **Timezone:** hozircha profil `timezone` maydoni (standart Asia/Tashkent). Due-check `zoneinfo` bilan hisoblanadi.
- **Kontent oxiri:** standart — to'xtatadi + tabrik. Qayta boshlash keyin sozlama sifatida qo'shilishi mumkin.
