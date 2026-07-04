# Faza 4c — Oylik Top Leaderboard — Dizayn Spec

**Sana:** 2026-07-04
**Faza:** 4c (Raqobat — 1-qism; duel → Faza 4d ga qoldirildi)
**Holat:** Tasdiqlash kutilmoqda (foydalanuvchi yo'q — standart qulflandi)
**Tayanadi:** Faza 0/1/2a/2b/3/4a/4b — tugallangan, `main`'da. (`DailySession` (status/score/date), bot factory + conftest router-detach, `send_daily` tayyor.)

---

## 1. Maqsad va natija

O'quvchilar orasida joriy oy bo'yicha **top leaderboard** — kim eng ko'p to'g'ri javob to'plagani. Bu raqobat/motivatsiya elementini qo'shadi (uzexam.uz "fair leaderboard" g'oyasi). Yangi model kerak emas — mavjud `DailySession` (COMPLETED, score, date) agregatlaridan tuziladi.

Faza oxirida:
- `/top` — joriy oy leaderboard'i (top 10 + so'rovchi o'z o'rni, agar 10 dan tashqarida bo'lsa).
- Reyting = joriy oydagi COMPLETED sessiyalar `score` yig'indisi; teng bo'lsa — sessiyalar soni (izchillik).
- Testlar o'tadi, `ruff` toza.

**Bu fazada YO'Q (Faza 4d):** do'stlar bilan 1v1 duel. Oy oxiri avtomatik broadcast ham hozircha yo'q (keyingi kichik ish — carryover).

---

## 2. Qarorlar

| Mavzu | Qaror |
|-------|-------|
| Metrika | Joriy oy COMPLETED `DailySession.score` yig'indisi ("oylik ballar" = to'g'ri javoblar soni) |
| Teng holat | Sessiyalar soni ko'p bo'lган yuqori (izchillikni rag'batlantiradi) |
| Ko'rsatish | Top 10 (🥇🥈🥉 + raqamlar) + so'rovchining o'z o'rni (agar 10 dan tashqarida) |
| Ism | `first_name` (bo'sh bo'lsa "Anonim") |
| Ishtirok | Barcha o'quvchilar avtomatik (joriy oyda ≥1 COMPLETED sessiya). Opt-out yo'q (MVP) |
| Yetkazish | Faqat `/top` (talab bo'yicha). Oy-oxiri broadcast → carryover |
| Yangi model | Yo'q — `DailySession` agregatlari |
| Joy | Xizmat `apps/learning/services/ranking.py`; handler `bot/handlers/leaderboard.py` (yangi router) |

---

## 3. Ma'lumot manbai (yangi model yo'q)

`DailySession`: `user` FK, `date` (DateField), `status` (COMPLETED), `score` (int, COMPLETED'da o'rnatilgan). Agregat:
```python
DailySession.objects.filter(status=COMPLETED, date__year=Y, date__month=M)
    .values("user").annotate(points=Sum("score"), sessions=Count("id"))
    .order_by("-points", "-sessions")
```

---

## 4. Xizmatlar (`apps/learning/services/ranking.py`, yangi)

- `build_monthly_leaderboard(year, month, limit=10) -> list[dict]` — yuqoridagi agregat, `limit` gача; har element `{rank, user_id, name, points, sessions}` (`name` = `first_name or "Anonim"`; `points` null bo'lsa 0 sifatida — COMPLETED'da score bor, lekin xavfsizlik uchun Coalesce/filter). `rank` 1 dan boshlanadi (enumerate).
- `user_month_rank(user, year, month) -> tuple[int, int] | None` — `(rank, points)`; foydalanuvchi joriy oyda ishtirok etmagan bo'lsa None. Rank = to'liq tartibdagi o'rin (limit'siz). To'liq ordered ro'yxatдан indeks + 1.
- Yordamchi: `_monthly_rows(year, month)` — ordered qatorlar (ikkala funksiya ishlatadi).

---

## 5. Bot handleri (`bot/handlers/leaderboard.py`, yangi router)

- `/top` → `build_monthly_leaderboard(now.year, now.month, 10)`; matn: sarlavha (oy nomi) + har element `🥇/🥈/🥉/N. <ism> — <points> ball (<sessions> kun)`; so'rovchi (`user`) top 10 da bo'lmasa — `user_month_rank` bilan o'z o'rnini qo'shimcha qatorда ko'rsatadi; hech kim yo'q bo'lsa "hali natija yo'q".
- Barcha ORM `sync_to_async` orqali. Matn HTML.
- Router `bot/factory.py`'ga ulanadi (8-router) va `bot/tests/conftest.py` `_detach_handler_routers` ro'yxatiga `leaderboard` qo'shiladi (aiogram singleton-router; aks holda ikkinchi `build_dispatcher()` testда `RuntimeError`).

---

## 6. Testlar (pytest + pytest-django)

- **`build_monthly_leaderboard`:** bir nechta user + turli oylik ballar → to'g'ri tartib (points desc, teng bo'lsa sessions desc); boshqa oy sessiyalari chiqarib tashlanadi; non-COMPLETED chiqarib tashlanadi; `rank` 1..N; `limit` hurmat qilinadi.
- **`user_month_rank`:** ishtirokchi → to'g'ri (rank, points); ishtirok etmagan → None; top 10 dan tashqaridagi ham to'g'ri rank.
- **`/top` handler:** natijalar bilan matn yuboradi (mock); bo'sh oyда "natija yo'q"; so'rovchi 10 dan tashqarida bo'lsa o'z o'rni qo'shiladi (async, mock).
- **Factory:** dispatcher `leaderboard` router'ini o'z ichiga oladi (≥8).
- Sender/tarmoq mock. Test chiqishi toza.

---

## 7. Konfiguratsiya

- Yangi settings shart emas (limit=10 default arg). Xohlasa `LEADERBOARD_SIZE` (default 10) qo'shsa bo'ladi — hozircha default arg yetarli.

---

## 8. Muvaffaqiyat mezoni (Definition of Done)

- [ ] `apps/learning/services/ranking.py` — `build_monthly_leaderboard` + `user_month_rank`.
- [ ] `/top` handler + `bot/handlers/leaderboard.py` router + strings.
- [ ] Router `factory.py`'ga ulash + `conftest.py` detach ro'yxatiga qo'shish.
- [ ] Testlar yashil, `ruff` toza, docs.

---

## 9. Ochiq savollar / xavflar

- **Adolat (fairness):** metrika "to'g'ri javoblar yig'indisi" — ko'proq so'z/kun tanlaganlar ustun bo'lishi mumkin. MVP uchun soddaligicha; normalizatsiya (aniqlik %, izchillik og'irligi) → carryover.
- **Maxfiylik:** leaderboard `first_name` + ball ko'rsatadi. Opt-out MVP'da yo'q → carryover (kelajakda `leaderboard_visible` toggle).
- **Router qo'shish:** 8-router — `conftest.py` detach ro'yxati YANGILANISHI shart (aks holda to'liq suite ikkinchi `build_dispatcher()`da yiqiladi).
- **`score` null:** faqat COMPLETED sessiyalar (score o'rnatilgan) hisobga olinadi; xavfsizlik uchun `score__isnull=False` yoki Coalesce.
- **Oy chegarasi:** `date__year`/`date__month` — sessiyaning `date` maydoni (o'quvchining local kuni, Faza 2a). Server tz bilan mos (Asia/Tashkent default).
