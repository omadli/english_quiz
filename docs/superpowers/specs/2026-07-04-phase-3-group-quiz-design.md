# Faza 3 — Guruh Quiz (QuizBot uslubi) — Dizayn Spec

**Sana:** 2026-07-04
**Faza:** 3 / 6 (`product-vision-and-roadmap.md` ga qarang)
**Holat:** Tasdiqlash kutilmoqda
**Tayanadi:** Faza 0/1/2a/2b — tugallangan, `main`'da. (Bot dispatcher, `poll_answer` handler, `build_questions`, `send_quiz_poll` tayyor.)
**Ilhom:** `github.com/omadli/quizbot` (aiogram 2.x) — aiogram 3.x + Django ORM'ga modernizatsiya.

---

## 1. Maqsad va natija

Botni guruhga admin qilib qo'shib, o'qituvchi (guruh admini) guruhda quiz o'tkazadi: qaysi kitob/unitlardan, qaysi savol turlari, nechta savol, har savol vaqti sozlanadi; so'ng bot ketma-ket **native quiz poll**lar yuboradi va har o'quvchining **to'g'ri javoblar soni + javob vaqtini** hisoblab, oxirida **leaderboard** chiqaradi. Natijalar DB'da saqlanadi (Faza 4 ustoz hisobotlari uchun).

Faza oxirida:
- Admin `/quiz` → sehrgar (kitob→unitlar→turlar→soni→interval→Boshlash) → `3-2-1-Go` → ketma-ket quiz poll'lar.
- Har javob `poll_answer` orqali guruh ballashiga yo'naltiriladi (o'quvchi + javob vaqti).
- Quiz tugagach leaderboard; `/stop` bilan to'xtatiladi.
- Testlar o'tadi, `ruff` toza.

**Bu fazada YO'Q:** ustoz dashboard/hisobotlari (Faza 4 — saqlangan natijalarni ishlatadi), tayyor savol banki (kechiktirildi), web.

---

## 2. Qarorlar

| Mavzu | Qaror |
|-------|-------|
| Savol manbai | **Word bazasidan** — tanlangan unitlar so'zlaridan, `build_questions` (Faza 2b) qayta ishlatiladi |
| Natijalar | **DB'ga saqlanadi** (`GroupQuizSession` + `GroupQuizParticipant`) — Faza 4 hisobotlari uchun |
| Sozlash | **To'liq sehrgar** (kitob → unitlar → turlar → soni → interval → Boshlash), faqat adminlar |
| Holat mexanizmi | **Model** (`GroupQuizSession`, chat_id bo'yicha) — aiogram FSM EMAS (guruhda per-chat holat oson) |
| Quiz ijrosi | **Bot jarayonida async runner** (`asyncio.sleep` bilan ketma-ket) — Celery EMAS (interaktiv real-time) |
| poll_answer | Bitta handler poll_id bo'yicha yo'naltiradi: avval guruh quiz, bo'lmasa Faza 2b shaxsiy imtihon |
| Poll turi | Native quiz poll (`PollType.QUIZ`, anonim emas, `open_period=interval`), avto-baholaydi |

---

## 3. Ma'lumot modeli (yangi `apps/quiz` app, label `quiz`)

### `GroupQuizSession(TimeStampedModel)`
| Maydon | Tur | Izoh |
|--------|-----|------|
| `chat_id` | BigInt, db_index | Guruh chat id |
| `started_by` | FK→User, null | Sozlagan admin (agar User bog'langan bo'lsa) |
| `book` | FK→catalog.Book, null | Tanlangan kitob |
| `unit_ids` | JSONField (list[int]) | Tanlangan unitlar |
| `question_types` | JSONField (list[str]) | en_uz/uz_en/def_word |
| `question_count` | PositiveSmallInt, default 10 | |
| `interval_seconds` | PositiveSmallInt, default 20 | Har savol vaqti (poll open_period) |
| `status` | Char choices: `configuring`/`running`/`finished`/`aborted` | |
| `started_at` / `finished_at` | DateTime, null | |
- Bir chat'da bir vaqtda bitta faol (`configuring`/`running`) sessiya (mantiqda tekshiriladi).

### `GroupQuizQuestion(TimeStampedModel)`
| Maydon | Tur | Izoh |
|--------|-----|------|
| `session` | FK→GroupQuizSession, related_name="questions" | |
| `word` | FK→catalog.Word | |
| `order` | PositiveSmallInt | |
| `question_type` | Char | |
| `poll_id` | Char(64), null, db_index | Yuborilgach to'ldiriladi |
| `sent_at` | DateTime, null | Javob vaqtini hisoblash uchun |
| `options` | JSONField | |
| `correct_option` | PositiveSmallInt | |

### `GroupQuizParticipant(TimeStampedModel)`
| Maydon | Tur | Izoh |
|--------|-----|------|
| `session` | FK→GroupQuizSession, related_name="participants" | |
| `telegram_id` | BigInt | |
| `username` / `full_name` | Char | Leaderboard ko'rsatish uchun |
| `correct_count` | PositiveSmallInt, default 0 | |
| `total_time` | Float, default 0 | Umumiy javob vaqti (soniya) |
- `UniqueConstraint(session, telegram_id)`.

unfold admin: uchala model.

---

## 4. Xizmatlar (`apps/quiz/services/`)

### `questions.py`
- `sample_words(unit_ids, count) -> list[Word]` — tanlangan unitlardan `count` ta tasodifiy so'z.
- Savol generatsiyasi: **Faza 2b `build_questions(words, types=None)`** kengaytiriladi — `types` berilsa faqat shu turlar round-robin (default = uchala tur, orqaga mos). Guruh quiz tanlangan turlarni beradi.

### `scoring.py`
- `record_group_answer(poll_id, option_ids, telegram_id, username, full_name) -> bool` — `GroupQuizQuestion`ni poll_id bo'yicha topadi; topilmasa `False` (shaxsiy imtihonga tushadi); topilsa `GroupQuizParticipant`ni get_or_create, `correct_count += (chosen == correct)`, `total_time += (now - question.sent_at)`, saqlaydi, `True` qaytaradi.
- `build_leaderboard(session) -> str` — ishtirokchilarni `correct_count` (↓), `total_time` (↑) bo'yicha saralaydi, 🥇🥈🥉 + vaqt bilan matn.

### `runner.py` (async, bot jarayonida)
- `run_group_quiz(bot, session)` — `3-2-1-Go` sanoq → har `GroupQuizQuestion` uchun: `bot.send_poll(..., type=QUIZ, open_period=interval)` → `poll_id`/`sent_at` saqlanadi → `asyncio.sleep(interval)` → keyingisi. Har iteratsiyada session `status`ni tekshiradi (`aborted` bo'lsa to'xtaydi). Oxirida `status=finished`, leaderboard yuboriladi.

---

## 5. Bot handlerlari (`bot/handlers/group_quiz.py`, yangi router)

- `/quiz` (admin filtri, guruh chat) → agar faol sessiya bo'lsa ogohlantiradi; aks holda `GroupQuizSession(status=configuring)` yaratadi → kitob tanlash inline keyboard.
- Sehrgar callback'lari (config'ni sessiyaga yozadi): `gq:book:<n>` → unitlar multi-select; `gq:unit:<id>` toggle / `gq:units_done` → turlar; `gq:type:<t>` toggle / `gq:types_done` → soni; `gq:count:<n>` → interval; `gq:int:<s>` → "Boshlash" tugmasi; `gq:start` → `run_group_quiz` (async task).
- `/stop` (admin) → faol sessiyani `aborted` qiladi (runner to'xtaydi).
- Faqat admin: `IS_ADMIN` filtri (bot API `get_chat_member` orqali yoki aiogram admin filtri).
- Router `bot/factory.py`'ga ulanadi.

### poll_answer yo'naltirish (`bot/handlers/quiz.py` o'zgartiriladi)
- Mavjud `on_poll_answer` avval `record_group_answer(...)` (guruh) ni chaqiradi; `False` qaytsa Faza 2b `record_answer(poll_id, option_ids)` (shaxsiy) ga tushadi. `poll_answer.user` dan telegram_id/username/full_name olinadi.

---

## 6. Testlar (pytest + pytest-django)

- **Modellar:** yaratish, unique(session, telegram_id), `session.questions`/`participants`.
- **`sample_words`:** tanlangan unitlardan count ta, boshqa unitlar chiqmaydi.
- **`build_questions(types=...)`:** faqat berilgan turlar; default (types=None) orqaga mos (uchala tur).
- **`record_group_answer`:** guruh poll → participant yaratadi/yangilaydi (correct + time), `True`; noma'lum poll → `False`.
- **`build_leaderboard`:** to'g'ri↓ / vaqt↑ saralash, 🥇🥈🥉.
- **Sehrgar handlerlar:** config'ni sessiyaga yozishi (async, mock callback + DB).
- **poll_answer yo'naltirish:** guruh topilsa shaxsiyga tushmaydi; topilmasa tushadi (mock).
- **Admin filtri:** admin bo'lmagan sozlay olmaydi.
- Runner `asyncio.sleep`/tarmoq mock; poll yuborish mock. Test chiqishi toza.

---

## 7. Konfiguratsiya

- `GROUP_QUIZ_INTERVALS` (masalan [10,20,30,45,60]) va count variantlari (`[5,10,20,30]`) — keyboard'larda.
- Bot guruhda ishlashi uchun: guruhga qo'shilishi + admin bo'lishi (privacy mode o'chiq bo'lishi kerak — komanda/callback olishi uchun; BotFather'da `/setprivacy Disable`). Readme'da eslatiladi.
- `poll_answer` update botga kelishi Faza 2b'da tasdiqlangan (aiogram allowed_updates avtomatik).

---

## 8. Muvaffaqiyat mezoni (Definition of Done)

- [ ] `apps/quiz` — 3 model + migratsiya + admin.
- [ ] `sample_words` + `build_questions(types=...)` kengaytmasi.
- [ ] `record_group_answer` + `build_leaderboard`.
- [ ] `/quiz` sehrgar (kitob→unitlar→turlar→soni→interval→Boshlash) + admin filtri.
- [ ] `run_group_quiz` (sanoq + ketma-ket poll + finish) + `/stop`.
- [ ] poll_answer yo'naltirish (guruh→shaxsiy) + dispatcher'ga ulash.
- [ ] Testlar yashil, `ruff` toza, docs.

---

## 9. Ochiq savollar / xavflar

- **Async runner testi:** `asyncio.sleep` + ketma-ket poll bilan runnerni to'liq test qilish og'ir; asosiy qamrov bo'laklarda (savol tayyorlash, bitta-poll yuborish, finish/leaderboard), runner yengil smoke (mock sleep/send). Implementatsiya rejasi aniqlaydi.
- **Admin aniqlash:** guruhda kim admin — `bot.get_chat_member(chat_id, user_id)` (async) yoki aiogram `ChatMemberAdministrator` filtri. Sozlash callback'larida tekshiriladi.
- **Bir vaqtda bitta quiz:** har chat'da bitta faol sessiya; ikkinchi `/quiz` ogohlantiradi.
- **Bot restart mid-quiz:** running sessiya to'xtab qoladi (async task yo'qoladi); qayta tiklanmaydi (MVP — `/quiz` qayta boshlanadi). Kelajakda tiklash mumkin.
- **Privacy mode:** bot guruhda xabar/komanda olishi uchun privacy o'chiq bo'lishi kerak (callback'lar baribir keladi). Readme'da.
- **poll_answer double-handler:** yo'naltirish poll_id bo'yicha — guruh va shaxsiy poll_id'lar ajralgan (turli modellar), to'qnashuv yo'q.
