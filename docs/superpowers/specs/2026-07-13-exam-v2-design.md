# Kechki Imtihon v2 (Sectioned Mini App Exam) — Dizayn Spec

**Sana:** 2026-07-13
**Holat:** DRAFT — foydalanuvchi talablari yozildi; qurishdan oldin 5 ta qaror tasdiqlanishi kerak (§5). Katta feature — ishlayotgan nightly exam pipeline'iga (SRS→streak→dashboard→report→leaderboard) tegadi, shuning uchun ehtiyotkorlik + tasdiq bilan quriladi.
**Tayanadi:** `run_exam`/`exam_deliver.py`, `build_questions`/`select_exam_words` (`exam.py`), `finalize_exam`+SM-2 (`report.py`/`srs.py`/`exam_grade.py`), `dispatch_evening_exams`/`dispatch_pre_exam_nudges` (tasks.py), `api_today` + Mini App SPA, `voice_sample`/edge-tts.

---

## 1. Foydalanuvchi talablari (aynan)

1. Imtihon vaqtidan ~30 daqiqa oldin, aynan vaqtida, va ~30 daqiqa keyin — **"imtihonga tayyormisiz?"** ogohlantirish (1-2 marta).
2. **Imtihon boshlanmaguncha barcha quiz savollari birdaniga yuborilmasin** (start-gate).
3. Imtihon **Mini App**'da bo'lsin — chunki writing va listening ham bo'ladi, hozirgi test/quiz ham.
4. Imtihonlar **bo'lim-bo'lim**: avval **Quiz → Writing → Listening → Speaking** (speaking ixtiyoriy yoki sozlamadan yoqiladigan).

---

## 2. Yechim arxitekturasi

**A. Ko'p bosqichli eslatma + start-gate (bot-side).**
- `DailySession.exam_stage` (SmallInt 0–3, migration) — 0 hech nima · 1 oldin-eslatma · 2 asosiy prompt (Boshlash tugmasi) · 3 keyin-eslatma.
- `run_exam` → **ikkiga bo'linadi**: `prompt_exam(user_id)` (tayyor + **▶️ Boshlash** tugmasini yuboradi, savol yubormaydi) va `deliver_exam_questions(session)` (hozirgi poll-yuborish tanasi). `dispatch_evening_exams` → `prompt_exam`.
- Yangi beat/oqim (`dispatch_exam_reminders`): T-30 "yaqinlashdi", T `prompt_exam`, T+30 "kutmoqda" — har biri (mavjud bo'lsa) Boshlash tugmasi bilan; `exam_stage` bilan idempotent.
- **Boshlash tugmasi** = Mini App'ni `?view=exam` ochadi (web_app tugma). (Fallback: agar Mini App ochilmasa, tugma bot-poll imtihonni ishga tushiradi — `deliver_exam_questions`.)

**B. Mini App bo'limli imtihon (`?view=exam`).**
- `api_today` bugungi so'zlarni beradi. SPA `showExam()` bo'limlarni ketma-ket yuritadi, progress bilan:
  - **Quiz** — EN→UZ variantli (mavjud `startQuiz` qayta ishlatiladi).
  - **Writing** — UZ/ta'rif ko'rsatiladi → foydalanuvchi EN so'zni **yozadi** → normalizatsiya (kichik harf, bo'sh joy/tinish belgisi olib tashlanadi) bilan solishtiriladi. **Avtomatik baholanadi.**
  - **Listening** — so'z audiosi (edge-tts EN, `voice-sample`ga o'xshash) ijro etiladi → foydalanuvchi UZ ma'noni **variantdan tanlaydi**. **Avtomatik baholanadi.**
  - **Speaking** (ixtiyoriy, `LearningProfile.speaking_enabled`) — EN so'zni **aytadi** → Web Speech recognition tekshiradi (mavjud speech test). O'chirilgan bo'lsa — bu bo'lim yo'q.
- Har bo'lim natijasi yig'iladi → tugagach **`api_submit_exam`** (initData) ga yuboriladi.

**C. Baholash + SRS (server, mavjud pipeline qayta ishlatiladi).**
- `api_submit_exam(request)` — initData auth → bugungi sessiya → har javob uchun **mavjud** SM-2 baholash (`grade_answer`/`apply_sm2`) qo'llanadi, `ExamQuestion` yoziladi, `DailySession.score/total/status` yangilanadi, `finalize_exam` (hisobot + streak) chaqiriladi. Shu orqali streak/dashboard/leaderboard/guardian-report **izchil qoladi**.
- Bot-poll imtihon **fallback sifatida saqlanadi** (o'chirilmaydi) — Mini App'siz foydalanuvchilar uchun.

**D. Sozlamalar.** `speaking_enabled` (bool) — bot `/settings` + Mini App Profil sozlamalariga qo'shiladi.

---

## 3. Ma'lumot modeli o'zgarishi

- `DailySession.exam_stage` SmallInt default 0 (eslatma bosqichi).
- `LearningProfile.speaking_enabled` bool default False (speaking opt-in).
- Migration: `learning`.

---

## 4. Fazalar (qurilish tartibi — TDD)

1. Model maydonlari + migration.
2. Start-gate: `prompt_exam`/`deliver_exam_questions` bo'linishi + `exam:start` bot handler + `dispatch_evening_exams` yangilanishi. (Bot-poll fallback ishlashini saqlash.)
3. Ko'p bosqichli eslatma (`dispatch_exam_reminders` + `exam_stage`).
4. `api_submit_exam` + SM-2 qayta ishlatish (server baholash).
5. Mini App `showExam()` — Quiz/Writing/Listening/Speaking bo'limlari + submit.
6. `speaking_enabled` sozlamasi (bot + Mini App).
7. Integratsiya + deploy + jonli tekshiruv.

---

## 5. Tasdiqlash kerak bo'lgan qarorlar (default'lar qo'yildi)

| # | Savol | Taklif (default) |
|---|-------|------------------|
| 1 | Writing baholash | Normalizatsiyalangan **aniq moslik** (kichik harf, trim, tinish belgisiz). Kichik xatoga yon bermaydi |
| 2 | Listening audiosi | So'zning **EN edge-tts** audiosi (voice-sample kabi) |
| 3 | Speaking default | **O'chirilgan** (opt-in, sozlamadan yoqiladi) |
| 4 | Bot-poll imtihon | **Fallback sifatida saqlanadi**; Mini App asosiy |
| 5 | Bo'lim uzunligi | Quiz 5 · Writing 3 · Listening 3 · Speaking 3 (kun so'zlaridan) |

---

## 6. Risklar

- Nightly exam **ishlayotgan pul-yo'li** (SRS/streak/dashboard/report/leaderboard). §2C mavjud grading'ni qayta ishlatadi — yangi baholash yozilmaydi. Bot-poll fallback saqlanadi.
- Jonli tekshirish qiyin: imtihon jadval bo'yicha, aniq vaqtda, DELIVERED sessiya bilan ishga tushadi. Test = pytest (services + handlers + api_submit); Mini App JS-syntax + struktura skrinshot.
- Speaking/Web-Speech brauzerga bog'liq (Telegram WebView'da ishlashi tekshirilishi kerak).
