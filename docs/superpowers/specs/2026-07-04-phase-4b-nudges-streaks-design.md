# Faza 4b — Nudges & Streak Motivatsiya — Dizayn Spec

**Sana:** 2026-07-04
**Faza:** 4b (Motivatsiya — 4a dan keyingi qism)
**Holat:** Tasdiqlash kutilmoqda
**Tayanadi:** Faza 0/1/2a/2b/3/4a — tugallangan, `main`'da. (Bot, onboarding, `DailySession`/`WordProgress`/`ExamQuestion`, `finalize_exam`, `send_quiz_poll`, `compute_streak`, `/settings` tayyor.)

---

## 1. Maqsad va natija

Bot "shaxsiy mentor" sifatida o'quvchini rag'batlantiradi: kunduzi so'zlarni takrorlashga eslatadi, imtihon vaqti yaqinlashganini aytadi, streak (ketma-ket kunlar) bosqichlarini nishonlaydi va kun davomida bitta "savolcha" (practice quiz-poll) yuboradi. Foydalanuvchi bularni /settings'dan o'chira oladi.

Faza oxirida:
- Yetkazilgan-lekin-imtihon-qilmagan o'quvchiga kunduzi **o'rganish eslatmasi**.
- Imtihon vaqtidan `PRE_EXAM_NUDGE_MINUTES` oldin **imtihon-oldi eslatmasi**.
- Imtihon tugagach streak milestone'ga yetsa **tabrik** ("barakalla").
- Kunlik bitta **anonim practice quiz-poll** ("savolcha").
- /settings'da **eslatmalarni o'chirish** tugmasi.
- Testlar o'tadi, `ruff` toza.

**Bu fazada YO'Q (Faza 4c):** oylik top leaderboard, do'stlar bilan duel. PDF yuklab olish — alohida kichik ish.

---

## 2. Qarorlar

| Mavzu | Qaror |
|-------|-------|
| Nudge idempotentligi | `DailySession`'ga `study_nudged` + `pre_exam_nudged` bool bayroqlari (bir kunda bir marta) |
| O'rganish eslatmasi | Kunlik crontab `STUDY_NUDGE_HOUR`da — bugun `delivered` (imtihon qilinmagan), `nudges_enabled`, hali `study_nudged` bo'lmaganlar |
| Imtihon-oldi eslatmasi | 60s interval beat, tz-aware — `exam_time`gача `PRE_EXAM_NUDGE_MINUTES` qolganda, `delivered`, `nudges_enabled`, hali `pre_exam_nudged` bo'lmaganlar |
| Streak tabrigi | `finalize_exam` ichida — imtihon `completed` bo'lgach `compute_streak` milestone'da bo'lsa tabrik (har milestone tabiiy ravishda bir marta) |
| Practice poll | Kunlik crontab `PRACTICE_POLL_HOUR`da — har faol o'quvchiga o'rganilgan so'zdan **1 anonim** quiz-poll (baholanmaydi) |
| Toggle | `LearningProfile.nudges_enabled` (bool, default True) + /settings tugmasi |
| Yangi model | Yo'q — mavjud `DailySession`/`LearningProfile`ga maydonlar qo'shiladi |

**Nega anonim practice poll:** anonim quiz-poll'da `poll_answer` update kelmaydi, shuning uchun mavjud shaxsiy/guruh routing'iga tegmaydi va SM-2 ni buzmaydi — Telegram o'zi to'g'ri javobni ko'rsatadi. Sof engagement.

---

## 3. Ma'lumot modeli (mavjud modellarga qo'shimcha)

### `DailySession` (Faza 2a) — yangi maydonlar
| Maydon | Tur | Izoh |
|--------|-----|------|
| `study_nudged` | Bool, default False | O'rganish eslatmasi yuborildimi (bir kunda bir marta) |
| `pre_exam_nudged` | Bool, default False | Imtihon-oldi eslatmasi yuborildimi |

### `LearningProfile` (Faza 1) — yangi maydon
| Maydon | Tur | Izoh |
|--------|-----|------|
| `nudges_enabled` | Bool, default True | Nudge/eslatma/practice-poll oladimi |

Migratsiyalar: har biriga.

---

## 4. Xizmatlar (`apps/learning/services/nudges.py`, yangi)

- `due_study_nudges(today) -> list[DailySession]` — bugungi `status=DELIVERED`, `study_nudged=False`, `session.user`ning `nudges_enabled=True` bo'lgan sessiyalar (select_related user__learning_profile + user__telegram; blocked_bot skip yuborishda).
- `is_due_for_pre_exam_nudge(profile, now) -> bool` — `now` (tz-aware, profile tz'da) `exam_time`dan `PRE_EXAM_NUDGE_MINUTES` ± 1 daqiqa oldin bo'lsa True (dispatch_evening_exams'dagi `is_due_for_exam` naqshiga o'xshash).
- `due_pre_exam_nudges(now) -> list[DailySession]` — bugungi `DELIVERED`, `pre_exam_nudged=False`, `nudges_enabled`, va `is_due_for_pre_exam_nudge` True bo'lganlar.
- `mark_study_nudged(session)` / `mark_pre_exam_nudged(session)` — `.update(...)` bilan bayroq.
- `streak_milestone_message(streak) -> str | None` — `streak` `STREAK_MILESTONES`da bo'lsa tabrik matni, aks holda None.
- `pick_practice_word(learner) -> Word | None` — o'quvchining `WordProgress`laridan tasodifiy bitta `Word` (yo'q bo'lsa None).
- `active_practice_learners() -> list[User]` — `nudges_enabled=True` + kamida bitta `WordProgress` bo'lgan o'quvchilar.

Nudge matnlari `bot/strings.py`da (o'rganish/imtihon-oldi/streak tabriklari — bir nechta variant bo'lsa yaxshi).

---

## 5. Bot / sender o'zgarishlari

- `bot/sender.py`: yangi `send_text(chat_id, text)` (oddiy matn nudge) — yoki mavjud `send_daily`ni matn uchun ishlatish. Nudge = oddiy matn.
- `apps/learning/services/exam.py`/sender `send_quiz_poll(...)`ga `is_anonymous: bool = False` parametri qo'shiladi (imtihon uchun False qoladi; practice uchun True). Practice poll `is_anonymous=True` bilan yuboriladi → `poll_answer` kelmaydi.
- `finalize_exam` (Faza 2b): imtihon `completed` bo'lib, hisobot yuborilgach — `streak_milestone_message(compute_streak(user))` None bo'lmasa qo'shimcha tabrik yuboradi (best-effort, `nudges_enabled` bo'lsa).

---

## 6. Celery tasklari (`apps/learning/tasks.py` kengaytiriladi)

- `dispatch_study_nudges()` — `due_study_nudges(localdate())` → har biriga o'rganish eslatmasi (`nudges_enabled` telegram, `blocked_bot` skip) + `mark_study_nudged`.
- `dispatch_pre_exam_nudges()` — `due_pre_exam_nudges(now())` → imtihon-oldi eslatmasi + `mark_pre_exam_nudged`.
- `dispatch_practice_polls()` — `active_practice_learners()` → har biriga `pick_practice_word` → `build_questions([word])[0]` → `send_quiz_poll(..., is_anonymous=True)`.
- Barcha yuborishlar `TelegramForbiddenError` (blocked) ni yutadi (best-effort, mavjud naqsh).
- `setup_periodic_tasks`:
  - `dispatch_study_nudges` — CrontabSchedule(`hour=STUDY_NUDGE_HOUR, minute=0`).
  - `dispatch_pre_exam_nudges` — IntervalSchedule(60s).
  - `dispatch_practice_polls` — CrontabSchedule(`hour=PRACTICE_POLL_HOUR, minute=0`).
  - Mavjud 3 interval + 1 guardian crontab task saqlanadi.

---

## 7. /settings o'zgarishi (Faza 1)

- `/settings` ko'rinishiga "🔔 Eslatmalar: Yoqilgan/O'chirilgan" tugmasi (`set:nudges` callback) — bosilganda `nudges_enabled` teskari bo'ladi va ko'rinish yangilanadi.
- Faza 1 settings handler + keyboard kengaytiriladi; mavjud sozlama oqimini buzmaydi.

---

## 8. Testlar (pytest + pytest-django)

- **Modellar/migratsiya:** yangi maydonlar defaultlari.
- **`due_study_nudges`:** delivered+not-nudged+enabled tanlanadi; completed/nudged/disabled chiqarib tashlanadi.
- **`is_due_for_pre_exam_nudge`:** oyna ichida True, tashqarisida False (tz-aware).
- **`streak_milestone_message`:** 7 → tabrik; 8 → None.
- **`pick_practice_word`:** WordProgress'dan tanlaydi; yo'q bo'lsa None.
- **`send_quiz_poll(is_anonymous=True)`:** anonim bayroq uzatiladi (mock bot.send_poll).
- **`finalize_exam` streak hook:** milestone streak → qo'shimcha tabrik yuboriladi (mock sender); non-milestone → yuborilmaydi.
- **`/settings` toggle:** `nudges_enabled` teskari bo'ladi (async, mock).
- **`dispatch_*` tasklar:** har due bo'lganга yuboradi + bayroq (mock sender); disabled skip.
- **`setup_periodic_tasks`:** 3 yangi task ro'yxatga olinadi, idempotent, mavjudlari saqlanadi.
- Sender/tarmoq mock. Test chiqishi toza.

---

## 9. Konfiguratsiya

- `STUDY_NUDGE_HOUR` (default 14).
- `PRACTICE_POLL_HOUR` (default 12).
- `PRE_EXAM_NUDGE_MINUTES` (default 30).
- `STREAK_MILESTONES` (default `[3, 7, 14, 30, 50, 100]`).

---

## 10. Muvaffaqiyat mezoni (Definition of Done)

- [ ] `DailySession.study_nudged`/`pre_exam_nudged` + `LearningProfile.nudges_enabled` + migratsiyalar + settings.
- [ ] `nudges.py` xizmatlari (study/pre-exam due, marks, streak message, practice word, active learners).
- [ ] `send_quiz_poll` anonim param; `finalize_exam` streak tabrigi.
- [ ] `dispatch_study_nudges`/`dispatch_pre_exam_nudges`/`dispatch_practice_polls` + `setup_periodic_tasks`.
- [ ] /settings nudge toggle.
- [ ] Testlar yashil, `ruff` toza, docs.

---

## 11. Ochiq savollar / xavflar

- **Cross-phase teginishlar:** `finalize_exam` (2b), `send_quiz_poll` (2b), `/settings` (1) kengaytiriladi — mavjud oqimlar buzilmasligi kerak (ehtiyotkorlik + test; mavjud testlar yashil qolsin).
- **Anonim poll routing:** anonim quiz-poll `poll_answer` bermaydi — shuning uchun grading/routing'ga tegmaydi (tasdiqlangan qaror).
- **Practice word manbai:** `WordProgress` (imtihon qilingan so'zlar). O'quvchi hali imtihon qilmagan bo'lsa practice poll skip.
- **Timezone:** study/practice — fixed soat (Asia/Tashkent server tz'da crontab); pre-exam — profile tz'da tekshiriladi (`is_due_for_pre_exam_nudge`).
- **Nudge bosqichi shovqini:** har nudge turi kuniga ko'pi bilan bir marta (bayroqlar); practice poll kuniga bir marta.
