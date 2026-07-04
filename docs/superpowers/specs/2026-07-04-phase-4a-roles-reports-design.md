# Faza 4a — Rollar, Referal & Hisobotlar (Roles, Referral & Reports) — Dizayn Spec

**Sana:** 2026-07-04
**Faza:** 4a (4/6 fazaning birinchi qismi; `product-vision-and-roadmap.md` ga qarang)
**Holat:** Tasdiqlash kutilmoqda
**Tayanadi:** Faza 0/1/2a/2b/3 — tugallangan, `main`'da. (Bot, onboarding `/start`, `DailySession`/`WordProgress`/`ExamQuestion`, guruh-quiz natijalari tayyor.)

---

## 1. Maqsad va natija

Ota-ona va ustozlar botga ulanib, farzand/o'quvchilarini **referal deep-link** orqali bog'lab oladi va ularning o'quv jarayoni bo'yicha **kunlik (avtomatik) + talab bo'yicha hisobot** oladi. Hisobotlar mavjud saqlangan ma'lumotlardan (`DailySession`, `WordProgress`, `ExamQuestion`, guruh-quiz) tuziladi.

Faza oxirida:
- Ota-ona/ustoz `/parent` / `/teacher` → bot deep-link beradi (`t.me/bot?start=g<token>`) → farzand bosadi → **Guardianship** yaratiladi.
- `/report` — ota-ona/ustoz o'z farzand/o'quvchilarining hisobotini oladi.
- Kunlik avtomatik hisobot (beat) har guardianga har ward bo'yicha yuboriladi.
- Testlar o'tadi, `ruff` toza.

**Bu fazada YO'Q (Faza 4b):** nudge/motivatsion xabarlar, streak-badge, davriy quiz poll, oylik top, duel. (Streak SONI hisobotda ko'rsatiladi, lekin nudge/gamifikatsiya 4b.) PDF yuklab olish — keyingi kichik ish.

---

## 2. Qarorlar

| Mavzu | Qaror |
|-------|-------|
| Referal yo'nalishi | Ota-ona/ustoz link oladi, farzand/o'quvchi bosib ulanadi (Telegram **deep-link** `start=g<token>`) |
| Hisobot yetkazish | Kunlik avtomatik (beat, `GUARDIAN_REPORT_HOUR`) + talab bo'yicha (`/report`) |
| Rollar | `parent` / `teacher` (bir foydalanuvchi ikkalasi ham bo'lishi mumkin; rol Guardianship'da) |
| Modellar joyi | Yangi `apps/relations` app (label `relations`) |
| Ulanish nuqtasi | Deep-link farzandning `/start`'iga keladi → Faza 1 `cmd_start` payload'ni tekshiradi → ulaydi |
| Hisobot manbai | `DailySession`/`WordProgress`/`ExamQuestion` (+ guruh-quiz) — faqat o'qish |

---

## 3. Ma'lumot modeli (yangi `apps/relations`)

### `ReferralToken(TimeStampedModel)`
| Maydon | Tur | Izoh |
|--------|-----|------|
| `token` | Char(32), unique, db_index | Tasodifiy (`secrets.token_urlsafe`) |
| `issuer` | FK→User, related_name="referral_tokens" | Link bergan ota-ona/ustoz |
| `role` | Char choices: `parent`/`teacher` | |
| `used_by` | FK→User, null | Bosган farzand/o'quvchi |
| `used_at` | DateTime, null | |
| `is_active` | Bool, default True | Bir marta ishlatiladi (used → is_active=False) |

### `Guardianship(TimeStampedModel)`
| Maydon | Tur | Izoh |
|--------|-----|------|
| `guardian` | FK→User, related_name="wards_links" | Ota-ona/ustoz |
| `learner` | FK→User, related_name="guardian_links" | Farzand/o'quvchi |
| `role` | Char choices: `parent`/`teacher` | |
| `status` | Char choices: `active`/`revoked`, default active | |
- `UniqueConstraint(guardian, learner)` named `uniq_guardian_learner`.

unfold admin: ikkalasi.

---

## 4. Xizmatlar (`apps/relations/services/`)

### `referral.py`
- `create_referral_token(issuer, role) -> ReferralToken` — tasodifiy token bilan yaratadi.
- `redeem_token(token_str, learner) -> Guardianship | None` — faol token topadi; topilmasa/ishlatilgan bo'lsa yoki learner==issuer bo'lsa None; aks holda `Guardianship` (get_or_create guardian+learner) yaratadi, tokenni ishlatilgan deb belgilaydi, qaytaradi.

### `reports.py`
- `compute_streak(learner) -> int` — bugundan orqaga ketma-ket `completed` `DailySession` kunlari soni.
- `build_learner_report(learner, date) -> str` — HTML: ism, bugungi so'zlar soni (DailySession words), imtihon bali (score/total), holat (delivered/completed), streak, (ixtiyoriy) guruh-quiz ishtiroki. Ward yo'q ma'lumot bo'lsa "bugun faol emas".
- `guardian_wards(guardian) -> list[User]` — faol Guardianship'lardagi learnerlar.

---

## 5. Bot handlerlari (`bot/handlers/relations.py`, yangi router)

- `/parent` / `/teacher` → `create_referral_token(user, role)` → deep-link matni: `https://t.me/<bot_username>?start=g<token>` + "Farzandingizga/O'quvchingizga shu havolani yuboring." (bot username `bot.get_me()` dan yoki settings'dan).
- `/report` → `guardian_wards(user)`; ward yo'q bo'lsa "hali hech kim ulanmagan"; bitta bo'lsa to'g'ridan-to'g'ri hisobot; bir nechta bo'lsa inline ro'yxat (`rep:<learner_id>`) → tanlanganda hisobot.
- **Deep-link ulanish:** Faza 1 `bot/handlers/start.py: cmd_start` `command: CommandObject` oladi; `command.args` `g<token>` bo'lsa → `redeem_token` → ulangani haqida xabar (ikkala tomonga) va onboarding'ni buzmaydi (yangi bo'lsa onboarding baribir keyin bo'ladi yoki ward faqat kuzatiladi). Payload bo'lmasa — oddiy onboarding.
- Router `bot/factory.py`'ga ulanadi.

---

## 6. Jadval (Celery Beat)

- `dispatch_guardian_reports()` (beat, kuniga bir marta `GUARDIAN_REPORT_HOUR`da — CrontabSchedule) — har faol Guardianship guardiani uchun har ward bo'yicha `build_learner_report` → guardianga yuboradi (`send_daily` matn). `blocked_bot` guardianlar skip.
- `setup_periodic_tasks`ga CrontabSchedule(`hour=GUARDIAN_REPORT_HOUR, minute=0`) + `dispatch_guardian_reports` qo'shiladi.

---

## 7. Testlar (pytest + pytest-django)

- **Modellar:** yaratish, `Guardianship` unique(guardian, learner).
- **`create_referral_token` / `redeem_token`:** token yaratadi; redeem → guardianship yaratadi + token ishlatilgan; qayta redeem → None; o'ziga ulanish → None.
- **`compute_streak`:** ketma-ket completed kunlar (3 kun → 3; uzilish → to'xtaydi).
- **`build_learner_report`:** so'z soni/bal/streak matnda; ma'lumotsiz ward.
- **`guardian_wards`:** faol wardlar.
- **Deep-link `cmd_start`:** payload → redeem chaqiriladi; payloadsiz → oddiy onboarding (mock).
- **`/parent` / `/report` handlerlar:** token+link; ward ro'yxati (async, mock).
- **`dispatch_guardian_reports`:** har ward bo'yicha yuboradi (mock sender).
- Sender/tarmoq mock. Test chiqishi toza.

---

## 8. Konfiguratsiya

- `GUARDIAN_REPORT_HOUR` (settings, standart 21).
- `BOT_USERNAME` (settings, deep-link uchun; yoki `bot.get_me()` dan runtime) — deep-link `t.me/<username>?start=...`.
- `poll_answer`/beat allaqachon sozlangan.

---

## 9. Muvaffaqiyat mezoni (Definition of Done)

- [ ] `apps/relations` — `ReferralToken` + `Guardianship` + admin + migratsiya.
- [ ] `create_referral_token` + `redeem_token`; `compute_streak` + `build_learner_report` + `guardian_wards`.
- [ ] `/parent` + `/teacher` (token+deep-link); deep-link ulanish (`cmd_start` payload); `/report`.
- [ ] `dispatch_guardian_reports` beat + `setup_periodic_tasks` (crontab).
- [ ] Router ulash. Testlar yashil, `ruff` toza, docs.

---

## 10. Ochiq savollar / xavflar

- **Deep-link `cmd_start` o'zgartirishi:** Faza 1 start handleri payload'ni tekshirishga kengaytiriladi — onboarding oqimini buzmasligi kerak (ehtiyotkorlik + test).
- **BOT_USERNAME:** deep-link uchun kerak; settings'dan yoki `bot.get_me()` (async) dan. Standart: settings `BOT_USERNAME`, bo'sh bo'lsa runtime `get_me`.
- **Guardian timezone:** kunlik hisobot fixed soatда (Asia/Tashkent). Ko'p tz keyin.
- **Ward maxfiyligi:** faqat faol Guardianship guardiani ward hisobotini ko'radi; token bir martalik.
- **Ward User bo'lishi:** farzand deep-link'ni bosгanda middleware `get_or_create_user` uni yaratadi (Faza 1), so'ng redeem ulaydi.
