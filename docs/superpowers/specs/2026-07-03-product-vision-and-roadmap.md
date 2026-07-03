# 4000 Essential Words — Mahsulot Vizyoni va Yo'l Xaritasi

**Sana:** 2026-07-03
**Holat:** Muhokama qilingan / tasdiqlash kutilmoqda

Ushbu hujjat butun mahsulotning umumiy ko'rinishini va fazalarga bo'lingan yo'l xaritasini jamlaydi. Har bir faza o'zining alohida spec → reja → implementatsiya siklidan o'tadi. **Bu hujjat "nima qurayotganimiz"ni saqlaydi; "qanday"ini har faza spec'i aniqlaydi.**

---

## 1. Mahsulot g'oyasi

*4000 Essential English Words* (6 kitob, ~4000 so'z) ni yodlash uchun **shaxsiy mentor** — Telegram bot + web app. Foydalanuvchi kunlik maqsad qo'yadi, bot har kuni belgilangan vaqtda yangi so'zlarni (tarjima, rasm, audio bilan) yuboradi, kun davomida o'rgatadi, kechqurun imtihon qiladi, motivatsiya beradi va progressni kuzatadi. Ustozlar guruhda quiz o'tkazadi, ota-onalar/ustozlar farzand/o'quvchi progressini kuzatadi.

**Yagona autentifikatsiya:** hamma narsa Telegram orqali. Web app'ga kirish ham bot bergan **6 xonali kod** bilan (parolsiz, uzexam.uz modeli).

---

## 2. Foydalanuvchi rollari

| Rol | Imkoniyatlar |
|-----|--------------|
| **O'quvchi (learner)** | So'z o'rganish, kunlik sikl, imtihon, o'yinlar, progress, web app |
| **Ota-ona (parent)** | Referal link orqali farzandini ulash, kunlik hisobot olish |
| **Ustoz (teacher)** | O'quvchilarni ulash, hisobot, **guruhda quiz o'tkazish** |
| **Admin** | django-unfold panel: kontent, foydalanuvchilar, statistika |

Rollar bir-birini istisno qilmaydi (bitta odam ham o'quvchi, ham ota-ona bo'lishi mumkin).

---

## 3. Ma'lumot manbalari

| Manba | Nima beradi | Ishlatilishi |
|-------|-------------|--------------|
| Lokal `data/book1-6.json` (Django dumpdata) | book, unit, en, **uz**, definition, example, pronunciation (IPA+POS), image path | **Asosiy manba** — o'zbekcha tarjimalar shu yerda |
| Lokal `uploads/images/words/...` (3600 rasm) | so'z rasmlari | Allaqachon mavjud, joyida ishlatiladi |
| Masofaviy `essentialenglish.review/.../data.json` | `sound` (native mp3 talaffuz), `exercise`, `reading` | **Boyitish** — asl audio + web uchun mashq/o'qish matnlari |

> Eslatma: masofaviy data ingliz–vetnamcha (`vi` bo'sh). O'zbekcha faqat lokal fixture'larda. Import lokal + masofaviyni `en` bo'yicha birlashtiradi.

---

## 4. Fazalarga bo'lingan yo'l xaritasi

### Faza 0 — Poydevor *(joriy spec: `2026-07-03-phase-0-foundation-design.md`)*
Modernizatsiya (Python 3.12, Django 5.2 LTS, uv, PostgreSQL, Redis, Celery+Beat, Docker, django-unfold), loyiha qayta strukturasi, **kontent modellari** (Book/Unit/Word) qayta dizayni, **JSON→DB import + media (rasm/audio) pipeline**, admin. Bot/o'quv mantiq YO'Q.

### Faza 1 — Bot yadrosi
aiogram 3.x skeleti (Django ORM bilan). Onboarding/tanishtirish. Telegram orqali ro'yxatdan o'tish. Sozlamalar: kunlik maqsad (masalan 10 so'z/kun yoki hafta 3 kun 20 tadan), jadval (kunlar/vaqtlar), ertalabki so'z vaqti (07:00), kechki imtihon vaqti (20:00), audio sozlamalari. Foydalanuvchi holati (FSM) Redis'da.

### Faza 2 — Kunlik o'quv sikli
- **Ertalab:** Celery Beat belgilangan vaqtda unit bo'yicha ketma-ket maqsad miqdoridagi so'zlarni yuboradi — tarjima, **generatsiya qilingan karta rasm** (so'z jadvali), va **audio** (native talaffuz + o'zbekcha, N marta takror — sozlanadi).
- **Kun davomida:** o'rganish rejimi, so'zlarni ko'rish/eshitish.
- **Kechqurun:** shaxsiy imtihon — quiz poll: EN→UZ, UZ→EN, definition→word. Natija saqlanadi.
- **SRS:** SM-2 spaced repetition (uzexam kabi) — noto'g'ri so'zlar optimal vaqtda qayta chiqadi.

### Faza 3 — Guruh Quiz rejimi (QuizBot uslubi)
Bot guruhga admin qilib qo'shiladi. Ustoz quiz rejimini boshlaydi: qaysi kitob/unit/bo'limlar, savol turi (EN↔UZ, definition), soni, har savol vaqti. `3-2-1-Go` sanoq → **Telegram native quiz poll**lar ketma-ket. Har o'quvchining **to'g'ri javoblar soni va javob vaqti** hisoblanadi → **leaderboard** (🥇🥈🥉). Savollar lug'atdan avtomatik generatsiya + oldindan tuzilgan savol banki. *(Ilhom: `github.com/omadli/quizbot`, aiogram 3.x ga modernizatsiya.)*

### Faza 4 — Motivatsiya va rollar
- **Nudge/motivatsiya:** "So'zlarni yodlayapsizmi?", "Imtihon vaqti yaqin", "Barakalla!" — davriy xabarlar, davriy quiz poll.
- **Streak, oylik top, duel/challenge** (do'stlar bilan bellashuv) — uzexam ilhomi.
- **Ota-ona/ustoz rejimi:** referal link, ulash, kunlik/haftalik hisobot.
- **PDF:** kitoblarni PDF yuklab olish.

### Faza 5 — Web app
Django + HTMX + Tailwind. Telegram parolsiz login (6 xonali kod). Onlayn **kitob varaqlab o'qish**, quiz, **speech testlar** (Web Speech API — talaffuz), **writing testlar**, shaxsiy analitika dashboard (zaif so'zlar, progress), o'quvchi/ota-ona/ustoz panellari.

### Faza 6 — Interaktiv o'yinlar
So'z-tarjima moslashtirish, xotira o'yini, so'z yozish/terish, tezlik o'yini, va h.k. — bot va web'da.

---

## 5. uzexam.uz'dan olingan g'oyalar

- Parolsiz Telegram login (6 xonali kod, 30 soniya)
- SM-2 spaced repetition (xatolarga bog'langan takrorlash)
- Uniqueness engine (to'g'ri javob berilgan material 90 kun qayta chiqmaydi)
- Adolatli reyting (birinchi urinish + qiyinlik + izchillik)
- Streak, oylik top, duel/challenge
- Karta-grid UI, ko'k/teal + oq fon, har kategoriya ikonkasi
- Shaxsiy analitika dashboard (zaif mavzular, progress timeline)

---

## 6. Umumiy texnologiya to'plami

Python 3.12 · Django 5.2 LTS · aiogram 3.x · PostgreSQL 16 · Redis 7 · Celery 5 + Beat · django-unfold · Django + HTMX + Tailwind (web) · uv · Docker Compose · pytest · ruff.

**Bot↔Django:** monorepo, umumiy Django ORM (bot uchun alohida API shart emas). Web app ham Django. Kelajakda mobil kerak bo'lsa DRF/Ninja API qo'shiladi.
