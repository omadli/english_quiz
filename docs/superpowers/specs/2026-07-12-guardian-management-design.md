# Vasiy Boshqaruvi (Guardian Management) — Dizayn Spec

**Sana:** 2026-07-12
**Sub-project:** ② (① daily-words v2 DONE; ③ dashboards NEXT)
**Holat:** Foydalanuvchi dizaynni tasdiqladi ("go") — "ikkalasi ham" (bot + web)
**Tayanadi:** Phase 4a `main`'da — `ReferralToken`, `Guardianship` (guardian→learner, role, status active/revoked, unique), `create_referral_token`/`redeem_token`, `guardian_wards`, `build_learner_report`, `/parent`·`/teacher`·`/report` handlerlari, `cmd_start` `?start=g<token>` redeem. Va ① — `LearningProfile.en_voice/uz_voice`, `_clean_settings`/`_profile_payload` (catalog/views), Mini App Profil sozlamalar formasi (`settingsHTML`).

---

## 1. Maqsad va natija

Ota-ona/o'qituvchi o'z o'quvchilarini (bir nechta) boshqaradi: referal orqali biriktiradi (mavjud), va **har bir o'quvchining kunlik sozlamalarini** (so'z/kun, o'quv kunlari, ertalab vaqti, imtihon vaqti, audio, 🇬🇧/🇺🇿 ovoz, takror, eslatmalar) **botda ham, Mini App'da ham** o'zgartira oladi + hisobotini ko'radi + ajrata oladi. Har amal **faol guardianship** bilan himoyalanadi.

Faza oxirida:
- Biriktirilganda ikkala tomonga xabar.
- Bot: `/wards` → o'quvchi tanla → ⚙️ Sozlamalar (inline preset pickerlar) · 📊 Hisobot · 🗑 Ajratish.
- Mini App: Profil → "👨‍👩‍👧 Nazorat" → o'quvchi → sozlamalar formasi (saqlash).
- Testlar o'tadi, ruff toza.

**Bu fazada YO'Q:** dashboard/hisobot grafiklar (③); vasiy uchun custom "Boshqa" vaqt (faqat presetlar); alohida `/app` login portali (Mini App Profil ishlatiladi); o'quvchiga laqab/nom qo'yish.

---

## 2. Qarorlar

| Mavzu | Qaror |
|-------|-------|
| Guard | Har o'qish/yozish **`active_guardianship(guardian, learner_id)`** orqali (faqat `status=ACTIVE`). Mavjud `pick_ward_report` naqshi |
| Validatsiya | Mavjud `_clean_settings` qayta ishlatiladi (so'z 1-50, vaqt HH:MM, kun 0-6, ovoz katalogdan, takror 1-5) |
| Bot ward-settings | Mavjud preset keyboard builderlarni **o'quvchiga qaratib** — callback `wsv:<lid>:<field>:<value>` (qiymatda `:` yo'q: words/repeat=int, ovoz=`en-US-...` (colonsiz), vaqt=preset **indeksi**, audio=on/off). Kunlar toggle `wsd:<lid>:<i\|all\|done>`. FSM YO'Q (to'g'ridan-to'g'ri saqlaydi) |
| Vaqt | Faqat presetlar (`MORNING_PRESETS`/`EXAM_PRESETS`), indeks bilan uzatiladi (callbackda colon bo'lmasin) |
| Web joyi | **Mini App → Profil → Nazorat** bo'limi (initData auth, frictionless). `/app` login portali emas. ③ dashboard ham shu yerga |
| Web API | `api_wards` + `api_ward_settings` (GET/POST) — initData (vasiy) + guardianship guard + `_clean_settings` |
| Ajratish | `Guardianship.status=REVOKED` (o'chirmaymiz — tarix qoladi) |
| Yangi model | YO'Q — mavjud `Guardianship`/`ReferralToken`/`LearningProfile` |

---

## 3. Umumiy backend

**`apps/relations/services/guardian.py`** (yangi):
- `active_guardianship(guardian, learner_id) -> Guardianship | None` — `filter(guardian=, learner_id=, status=ACTIVE).first()`.
- `ward_profile(guardian, learner_id) -> LearningProfile | None` — guard o'tsa o'quvchining `LearningProfile` (get_or_create), aks holda `None`.
- `revoke(guardian, learner_id) -> bool` — active guardianshipni REVOKED qiladi.
- (mavjud `guardian_wards` reports.py'da qoladi.)

**Sozlamalar validatsiyasi** — `_clean_settings` (catalog/views.py) hozircha shu yerda; web ward endpointi undan foydalanadi (import). (Refaktor shart emas.)

---

## 4. Komponentlar

### 4.1 Biriktirish xabarlari (`bot/handlers/start.py`, `strings.py`)
`cmd_start`'da redeem muvaffaqiyatli bo'lsa: o'quvchiga `LINKED_OK` (mavjud) + **vasiyga** `WARD_JOINED` xabari (`guardianship.guardian.telegram.telegram_id` ga `bot.send_message`, best-effort). Rol nomi (ota-ona/o'qituvchi) bilan.

### 4.2 Bot vasiy boshqaruvi (`bot/handlers/guardian.py`, `bot/keyboards/guardian.py`, `strings.py`)
- **`/wards`** → `guardian_wards(user)`; bo'sh → `NO_WARDS`; aks holda `wards_manage_keyboard(wards)` (`ward:<lid>`).
- **`ward:<lid>`** → guard → `ward_menu_keyboard(lid)`: ⚙️ Sozlamalar (`wset:<lid>`) · 📊 Hisobot (`rep:<lid>` — mavjud handler) · 🗑 Ajratish (`wrevoke:<lid>`).
- **`wset:<lid>`** → guard → `ward_settings_keyboard(profile, lid)` (qiymatlar + `wsedit:<lid>:<field>`).
- **`wsedit:<lid>:<field>`** → mos picker (words/morning/exam/audio/envoice/uzvoice/repeat/days) ward-callbacklari bilan.
- **`wsv:<lid>:<field>:<value>`** → guard → saqla → ward settings ekraniga qayt.
- **`wsd:<lid>:<i|all|done>`** → o'quvchi `study_weekdays` toggle (profildan), re-render; done → ward settings.
- **`wrevoke:<lid>`** → `revoke` → tasdiq xabari.
- Barcha callback active guardianship guard.

### 4.3 Web (Mini App) vasiy (`apps/catalog/views.py`, `config/urls.py`, `templates/webapp/index.html`)
- **`api_wards(request)`** — `@csrf_exempt`, `_profile_from_request` → guardian = profile.user → `guardian_wards` → `{"wards": [{"id", "name"}]}`. Route `webapp/api/wards/`.
- **`api_ward_settings(request, learner_id)`** — `@csrf_exempt`, guard `active_guardianship(caller, learner_id)`; yo'q → 403; GET → ward `_profile_payload`; POST → `_clean_settings` → saqla. Route `webapp/api/ward/<int:learner_id>/settings/`.
- SPA: Profil tab'da `apiWards()` bo'sh bo'lmasa **"👨‍👩‍👧 Nazorat"** karta → o'quvchilar ro'yxati → tanla → `apiWardSettings(id)` GET → mavjud `settingsHTML(s)` qayta ishlatiladi → Saqlash → POST `api_ward_settings`.

---

## 5. Testlar (TDD)

- `apps/relations/tests/test_guardian_service.py` — `active_guardianship` (active/revoked/none), `ward_profile` (guard o'tadi/o'tmaydi), `revoke`.
- `bot/tests/test_handlers_guardian.py` — `/wards` (bo'sh/ro'yxat), `wset` guard (biriktirilmagan → hech narsa), `wsv:...:words` o'quvchi profilini saqlaydi (boshqasini emas), `wrevoke` REVOKED qiladi.
- `apps/catalog/tests/test_webapp_wards.py` — `api_wards` (auth yo'q→401, ro'yxat), `api_ward_settings` (guard yo'q→403, GET, POST update + invalid drop).
- `bot/tests/test_handlers_start.py` — redeem'da vasiyga xabar yuboriladi (mock bot).

---

## 6. Risklar / eslatmalar

- Callback `wsv:<lid>:<field>:<value>` — qiymatda `:` bo'lmasligi shart (vaqt=preset indeks, ovoz id colonsiz). Parse: `split(":", 3)`.
- Vasiy o'zi ham o'quvchi (onboard bo'lgan) bo'lishi mumkin; `/wards` faqat uning wardlarini ko'rsatadi.
- Prod bot webhook — lokal jonli bot ishga tushirilmaydi; test = pytest.
- ③ dashboard shu Nazorat bo'limini kengaytiradi (grafiklar, xato so'zlar, bajarilmagan kunlar).
