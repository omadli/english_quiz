# Faza 2b — Kechki imtihon + SRS (Evening Exam) — Dizayn Spec

**Sana:** 2026-07-04
**Faza:** 2b (2/6 fazaning ikkinchi yarmi; `product-vision-and-roadmap.md` ga qarang)
**Holat:** Tasdiqlash kutilmoqda
**Tayanadi:** Faza 0 + 1 + 2a — tugallangan, `main`'da. (`DailySession`, `WordProgress` SM-2 maydonlari, bot dispatcher, sender tayyor.)

---

## 1. Maqsad va natija

Har foydalanuvchiga kechqurun (`exam_time`, timezone bo'yicha) o'sha kuni yetkazilgan so'zlar (+ SRS muddati kelgan takror so'zlar) bo'yicha **imtihon** yuborish: native Telegram quiz poll'lar (EN→UZ, UZ→EN, definition; distraktorlar bilan). Javoblar avtomatik baholanadi, `WordProgress` **SM-2** bilan yangilanadi, imtihon oynasi tugagach **kunlik hisobot** yuboriladi.

Faza oxirida:
- `dispatch_evening_exams` (Beat 60s) due foydalanuvchilarga `send_exam` taskini navbatga qo'yadi.
- `send_exam` — savollarni generatsiya qilib native quiz poll'lar yuboradi, `ExamQuestion` yozadi, session'ni `exam_sent` qiladi.
- Bot `poll_answer` handler har javobni baholaydi, SM-2 yangilaydi, ballni oshiradi.
- `finalize_due_exams` (Beat) oyna tugagach session'ni `completed` qiladi va hisobot yuboradi.
- Testlar o'tadi, `ruff` toza.

**Bu fazada YO'Q:** guruh quiz (Faza 3), motivatsion nudge/rollar (Faza 4), web/speech-writing (Faza 5).

---

## 2. Qarorlar

| Mavzu | Qaror |
|-------|-------|
| Savol/so'z | Har so'zga **1 ta**, tur navbatma-navbat (EN→UZ / UZ→EN / def→word) — batch bo'ylab uchala tur chiqadi |
| Qamrov | Kun so'zlari + **SRS-due** takror so'zlar (`next_review <= today`, status≠new, cheklangan K) |
| Format | Barcha poll'lar exam_time'da birdan; foydalanuvchi **oyna** (`EXAM_WINDOW_MINUTES`, standart 60) ichida javob beradi |
| Poll turi | Native Telegram **quiz poll** (`PollType.QUIZ`, anonim emas, `open_period`, `explanation`, avto-baholaydi) |
| Baholash | Bot `poll_answer` handler → poll_id→`ExamQuestion` → SM-2 yangilash + ball |
| Yakunlash/hisobot | `finalize_due_exams` beat (session `exam_sent` + oyna o'tgan) → `completed` + hisobot |
| SM-2 | Standart SM-2 (ease_factor, interval, repetitions, next_review) |
| Distraktorlar | Boshqa so'zlardan (imkon qadar shu kitob/darajadan), 3 ta, takrorlanmas |

---

## 3. Ma'lumot modeli (`apps/learning`'ga qo'shiladi)

### `ExamQuestion(TimeStampedModel)`
| Maydon | Tur | Izoh |
|--------|-----|------|
| `daily_session` | FK→DailySession, related_name="questions" | |
| `word` | FK→catalog.Word | |
| `question_type` | Char choices: `en_uz`/`uz_en`/`def_word` | |
| `poll_id` | Char(64), unique, db_index | Telegram poll id — kelayotgan `poll_answer` shu bilan bog'lanadi |
| `options` | JSONField (list[str]) | 4 variant matni |
| `correct_option` | PositiveSmallInt | To'g'ri variant indeksi (0–3) |
| `chosen_option` | PositiveSmallInt, null | Foydalanuvchi tanlovi |
| `is_correct` | Bool, null | Javob bergach to'ldiriladi |
| `answered_at` | DateTime, null | |

- `DailySession` (2a'dan): `status` (`exam_sent`/`completed` shu yerda ishlatiladi), `exam_sent_at`, `completed_at`, `score`, `total`.
- `WordProgress` (2a'dan): SM-2 maydonlari shu yerda YANGILANADI.
- unfold admin: `ExamQuestion`.

---

## 4. Xizmatlar (`apps/learning/services/`)

### `srs.py` — SM-2
- `apply_sm2(progress: WordProgress, correct: bool) -> None` — standart SM-2:
  - `correct`: `repetitions += 1`; interval = 1 (rep 1), 6 (rep 2), else `round(interval * ease)`; ease `+= 0.1` (chegara 1.3–2.5+).
  - `wrong`: `repetitions = 0`, `interval = 1`, ease `-= 0.2` (min 1.3).
  - `next_review = today + interval_days`; `status`: `known` (rep≥3) yoki `learning`; `correct_count`/`wrong_count`, `last_reviewed` yangilanadi. Saqlaydi.
- `grade_answer(user, word, correct: bool) -> WordProgress` — `WordProgress` topib/yaratib `apply_sm2` chaqiradi.

### `exam.py` — savol generatsiyasi
- `select_exam_words(profile) -> list[Word]` — bugungi `DailySession.words` + `WordProgress` (user, `next_review <= today`, status≠new, `[:K]`). Dedupe, tartib.
- `build_questions(session, words) -> list[dict]` — har so'z uchun tur (round-robin), prompt + 4 variant (to'g'ri + 3 distraktor), `correct_option`. Qaytaradi: `{word, question_type, prompt, options, correct_option, explanation}`.
  - `en_uz`: prompt=inglizcha so'z (+POS), variantlar=o'zbekcha tarjimalar.
  - `uz_en`: prompt=o'zbekcha, variantlar=inglizcha so'zlar.
  - `def_word`: prompt=definition, variantlar=inglizcha so'zlar.
  - Distraktorlar `_distractors(word, field, count)` — boshqa so'zlardan (shu kitob afzal), takrorlanmas.

### `send_exam` orkestratsiyasi (`exam_deliver.py` yoki `deliver.py`ga qo'shni)
- `run_exam(user_id) -> DailySession | None` — bugungi `delivered` session topadi; `exam_sent`/`completed` bo'lsa yoki `blocked_bot` bo'lsa skip. `select_exam_words` → `build_questions` → har savol uchun **quiz poll yuboradi** (`send_quiz_poll` → poll_id) → `ExamQuestion` yozadi. Session `status=exam_sent`, `exam_sent_at=now`, `total=len(questions)`, `score=0`.

### `report.py` — kunlik hisobot
- `build_report(session) -> str` — ball (X/N), to'g'ri/noto'g'ri, takrorlash kerak bo'lgan so'zlar (noto'g'ri javob berilganlari).
- `finalize_exam(session)` — ball = `is_correct=True` sonini hisoblaydi, `status=completed`, `completed_at=now`, hisobot yuboradi.

---

## 5. Jadval (Celery Beat)

- `is_due_for_exam(profile, now_utc) -> bool` — `is_due_for_delivery`ga o'xshash, lekin `exam_time`.
- `dispatch_evening_exams()` (Beat 60s) — faol+onboarded profillar; `is_due_for_exam` bo'lsa `run_exam.delay(user_id)`. (`run_exam` ichida "bugun delivered va exam_sent emas" tekshiruvi idempotentlikni himoya qiladi.)
- `finalize_due_exams()` (Beat 60s) — `status=exam_sent` va `exam_sent_at + EXAM_WINDOW < now` bo'lgan sessiyalar → `finalize_exam`.
- Beat ro'yxati `setup_periodic_tasks`ga qo'shiladi (`dispatch_evening_exams`, `finalize_due_exams`).

---

## 6. Bot: poll javoblari

- `bot/handlers/quiz.py` (yangi router) — `@router.poll_answer()`:
  - `poll_id` bo'yicha `ExamQuestion` topadi (`sync_to_async`); topilmasa e'tiborsiz.
  - `chosen_option = poll_answer.option_ids[0]`, `is_correct = (chosen == correct_option)`, `answered_at`, saqlaydi.
  - `grade_answer(user, word, is_correct)` — SM-2 yangilash.
  - To'g'ri bo'lsa `DailySession.score += 1` (atomik `F()` bilan).
- Router `bot/factory.py: build_dispatcher`'ga ulanadi.

### Poll yuborish (`bot/sender.py`'ga qo'shiladi)
- `send_quiz_poll(chat_id, question, options, correct_option, open_period, explanation) -> str` — `bot.send_poll(..., type=QUIZ, is_anonymous=False, correct_option_id=..., open_period=..., explanation=...)`, `poll.poll_id` qaytaradi. Sync wrapper (`asyncio.run`).

---

## 7. Testlar (pytest + pytest-django)

- **`apply_sm2`:** to'g'ri/noto'g'ri o'tishlar (interval o'sishi 1→6→ease*, ease chegaralari, wrong reset, next_review, status). Toza unit.
- **`grade_answer`:** `WordProgress` topib/yaratib SM-2 chaqiradi, count'lar.
- **`build_questions`:** to'g'ri variant mavjud, 4 variant, distraktorlar takrorlanmas, tur round-robin.
- **`select_exam_words`:** kun so'zlari + due reviews, cheklangan, dedupe.
- **`is_due_for_exam`:** vaqt/weekday/tz.
- **`run_exam`:** mock poll-sender → `ExamQuestion` yozadi, `exam_sent`, idempotent.
- **`poll_answer` handler:** mock `ExamQuestion` lookup + grade → yozadi, ball oshadi (async, mock).
- **`finalize_exam`/`finalize_due_exams`:** ball hisoblaydi, `completed`, hisobot yuboradi (mock sender).
- Media/sender/tarmoq mock. Test chiqishi toza.

---

## 8. Konfiguratsiya

- `EXAM_WINDOW_MINUTES` (settings, standart 60) — imtihon oynasi + poll `open_period`.
- `EXAM_REVIEW_CAP` (standart 10) — imtihonga qo'shiladigan SRS-due so'zlar maksimumi.
- Beat: `dispatch_evening_exams` + `finalize_due_exams` `setup_periodic_tasks`da.
- `BOT_TOKEN` yuborish va poll_answer olish uchun kerak (bot polling ishlashi shart).

---

## 9. Muvaffaqiyat mezoni (Definition of Done)

- [ ] `ExamQuestion` modeli + migratsiya + admin.
- [ ] `apply_sm2` + `grade_answer` (SRS).
- [ ] `build_questions` (3 tur + distraktorlar) + `select_exam_words` (kun + SRS-due).
- [ ] `is_due_for_exam` + `run_exam` + `send_quiz_poll` sender.
- [ ] Bot `poll_answer` handler + dispatcher'ga ulash.
- [ ] `finalize_exam` + `build_report` + `finalize_due_exams` beat.
- [ ] `setup_periodic_tasks` yangilanadi (2 yangi task). Testlar yashil, `ruff` toza, docs.

---

## 10. Ochiq savollar / xavflar

- **poll_answer yetkazish:** Telegram `poll_answer` yangilanishlari faqat non-anonymous quiz poll uchun keladi va bot polling ishlab turishi kerak. `allowed_updates`'ga `poll_answer` kirishi tekshiriladi (aiogram standart barcha update'larni oladi).
- **Oyna/finalize:** poll `open_period` = oyna; `finalize_due_exams` javob bermagan poll'larni ham yakunlaydi (javob berilmagan = noto'g'ri emas, shunchaki baholanmagan — hisobotда "javob berilmadi").
- **Distraktor yetishmasligi:** kichik kitob/unitda 3 ta distraktor topilmasa, global fallback.
- **Real imtihon tekshiruvi** BotFather token + ishlaydigan bot talab qiladi; kod/testlar mock bilan to'liq tekshiriladi.
- **Concurrency (2a carryover):** `score += 1` atomik `F()` bilan; `run_exam` idempotentligi session status bilan.
