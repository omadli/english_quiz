# O'quvchi Dashboard / Hisobotlar — Dizayn Spec

**Sana:** 2026-07-12
**Sub-project:** ③ (oxirgi; ① daily-words v2 + ② guardian mgmt DONE+deployed)
**Holat:** Foydalanuvchi dizaynni tasdiqladi ("ha")
**Tayanadi:** `LearnedWord`, `ExamQuestion` (is_correct/answered_at), `DailySession` (status/score/total), `WordProgress`, `LearningProfile.study_weekdays`, `compute_streak` (relations/reports); ② `ward_profile`/`active_guardianship` guard, `_profile_from_request` initData auth, Mini App Profil + Nazorat; ① inline-SVG/self-contained SPA (tashqi kutubxonasiz).

---

## 1. Maqsad va natija

O'quvchining o'zi (Profil) va vasiy (Nazorat → o'quvchi → 📊 Dashboard) uchun eng kerakli hisobotlar — grafiklar bilan:
- Yodlagan so'zlar (progress %), streak.
- Imtihon aniqligi (umumiy + oxirgi 30 kunlik trend).
- Ko'p xato qilingan so'zlar (top 10).
- Bajarilmagan kunlar (o'quv kuni bo'lib, COMPLETED sessiya yo'q).
- 30-kunlik faollik heatmap.

Faza oxirida: yagona `build_dashboard(user, days=30)` xizmati; `api_dashboard` (o'zi) + `api_ward_dashboard(learner_id)` (vasiy, guard); Mini App Profil'da o'z dashboardi + Nazorat'da o'quvchi dashboardi (inline SVG/CSS). Testlar o'tadi, ruff toza.

**Bu fazada YO'Q:** yangi bot buyrug'i (mavjud `/report` qoladi); PDF/eksport; SRS chuqur tahlili; tashqi chart kutubxonasi.

---

## 2. Qarorlar

| Mavzu | Qaror |
|-------|-------|
| Xizmat | `apps/learning/services/dashboard.py` `build_dashboard(user, days=30) -> dict` — sof funksiya, hammasi shu yerda hisoblanadi |
| Oyna | Oxirgi **30 kun** (trend, missed, heatmap) |
| Yodlagan | `LearnedWord` soni / `Word` jami soni |
| Aniqlik | `ExamQuestion` `is_correct` (javob berilganlar: `is_correct__isnull=False`), `daily_session__user` bo'yicha; kunlik seriya `daily_session__date` |
| Xato so'zlar | `is_correct=False` → so'z bo'yicha `Count`, top 10, `[{en, uz, wrong}]` |
| Bajarilmagan kun | Oxirgi 30 kun ichida `date.weekday() in study_weekdays`, `date >= birinchi faoliyat sanasi`, COMPLETED sessiya yo'q |
| Faollik | Har kun → `{date, status, score, total}` (heatmap uchun) |
| Web joyi | Mini App — o'zi = Profil kengaytmasi; vasiy = Nazorat → 📊 Dashboard |
| Grafiklar | Inline SVG/CSS (bar trend, kun-grid heatmap, ro'yxatlar) — tashqi dep yo'q |
| Guard | `api_ward_dashboard` — ② `ward_profile` guard (faol guardianship) |
| Yangi model | YO'Q |

---

## 3. Backend — `build_dashboard(user, days=30)`

Qaytaradi (JSON-safe dict):
```
{
  "learned": int, "total": int,
  "streak": int,
  "accuracy": {"correct": int, "answered": int, "pct": int},
  "trend": [{"date": "YYYY-MM-DD", "correct": int, "total": int}],   # oxirgi 30 kun, faqat imtihon bo'lgan kunlar
  "error_words": [{"en": str, "uz": str, "wrong": int}],             # top 10
  "missed_days": {"count": int, "dates": ["YYYY-MM-DD", ...]},
  "activity": [{"date": "YYYY-MM-DD", "status": str, "score": int|null, "total": int|null}]  # 30 kun
}
```
- `learned` = `LearnedWord.objects.filter(user=user).count()`; `total` = `Word.objects.count()`.
- `streak` = `compute_streak(user)`.
- Aniqlik/trend/xato so'zlar — `ExamQuestion` aggregatsiyalari (`daily_session__user=user`).
- `missed_days` — oxirgi 30 kun sanalarini aylanib, `study_weekdays` + `>= first_activity` + COMPLETED yo'q.
- `first_activity` = eng erta `DailySession.date` (yo'q bo'lsa missed bo'sh).

---

## 4. Web API (`apps/catalog/views.py`, `config/urls.py`)

- `api_dashboard(request)` — `@csrf_exempt`, `_profile_from_request` → `build_dashboard(profile.user)`. Route `webapp/api/dashboard/`.
- `api_ward_dashboard(request, learner_id)` — `@csrf_exempt`, guard `ward_profile(caller.user, learner_id)` (None → 403) → `build_dashboard(ward_profile.user)`. Route `webapp/api/ward/<int:learner_id>/dashboard/`.

---

## 5. Mini App (`templates/webapp/index.html`)

- **`dashboardHTML(d)`** — inline SVG/CSS bilan render:
  - Yuqorida: yodlagan progress + streak + aniqlik % (stat tiles).
  - **Aniqlik trendi:** oxirgi kunlar bar chart (SVG, har bar = kunlik to'g'ri/jami; balandlik = pct).
  - **30-kunlik faollik:** kun-grid (heatmap) — COMPLETED yashil, DELIVERED/boshqa sariq, missed/yo'q kulrang, o'quv kuni bo'lmagan xira.
  - **Ko'p xato so'zlar:** ro'yxat (en — uz · N marta).
  - **Bajarilmagan kunlar:** soni + sanalar.
- **Profil tab:** mavjud progress kartadan keyin `getJSON("api/dashboard/")` → `dashboardHTML` ("Statistika" bo'limi).
- **Nazorat → o'quvchi:** ⚙️ Sozlamalar yonida **📊 Dashboard** → `api/ward/<id>/dashboard/` → `dashboardHTML`.
- Faqat kompilyatsiya qilingan Tailwind klasslar + inline SVG → CSS rebuild yo'q.

---

## 6. Testlar (TDD)

- `apps/learning/tests/test_dashboard.py` — `build_dashboard`: learned/total, streak, accuracy (to'g'ri/jami), error_words (top, tartiblangan), missed_days (o'quv kuni + COMPLETED yo'q → missed; dam kuni → missed emas; birinchi faoliyatdan oldin → missed emas), trend/activity shakli.
- `apps/catalog/tests/test_webapp_dashboard.py` — `api_dashboard` (401 auth yo'q, 200 + shakl); `api_ward_dashboard` (guard yo'q → 403, guard bor → 200).

---

## 7. Risklar / eslatmalar

- `missed_days` chegarasi (first_activity) muhim — aks holda ro'yxatdan oldingi barcha kunlar "bajarilmagan" bo'lib ketadi.
- Grafiklar inline SVG — `dataviz` skill'ini implement paytida o'qiyman (rang/o'lcham izchilligi).
- Bo'sh holat: yangi o'quvchi (imtihon yo'q) → accuracy 0/0, trend/error_words bo'sh — UI "hali ma'lumot yo'q" ko'rsatadi.
- Prod bot webhook — lokal jonli bot ishga tushirilmaydi; test = pytest.
