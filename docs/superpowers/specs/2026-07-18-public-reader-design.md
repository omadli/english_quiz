# Public book reader (D)

**Sana:** 2026-07-18 · **Holat:** shipped

## Kontekst

Foydalanuvchi profilga kirmasdan kitob/so'z/rasmlarni "chiroyli sahifalangan kitob
shaklida" ko'rishni so'radi. Muhim topilma: `/webapp/` **allaqachon ommaviy** (auth talab
qilmaydi) va CloudStorage bug tuzatilgach brauzerda ishlaydi — ya'ni "profilga kirmasdan
ko'rish" asosan tayyor edi. Qolgan uch bo'lak:

## O'zgarishlar

1. **Reader** — `showWords` endi so'zlarni 5 tadan sahifaga bo'lib, ‹ › tugmalari va sahifa
   raqami bilan varaqlanadigan qiladi (kitob varag'idek). Mavjud `wordCard` qayta ishlatiladi
   — yangi kartа yo'q, alohida "reader-mode" toggle yo'q; bu shunchaki so'z ko'rinishi.

2. **`/kitoblar/`** — `webapp_index` template'ga thin URL alias (server-render yo'q; savol-javobda
   tanlangan "SPA'ni qayta ishlatish"). Data chaqiruvlari nisbiy `api/…` edi → `/kitoblar/api/…`
   ga ketardi (404); `getJSON` va `playWord` endi `/webapp/` prefiksiga anchor qilingan.

3. **Brauzer UX** — Telegram tashqarisida (`platform === "unknown"`) auth talab qiladigan
   "Bugun" va "Profil" tab'lari yashiriladi. "Kitoblar" va "Mashqlar" ommaviy (so'z ko'rish +
   o'yin, initData shart emas) — qoladi.

4. **Landing havolasi** — `/` da ikkita "📖 Kitoblarni ko'rish" → `/kitoblar/` (login shart emas).

## Xavfsizlik

Ommaviy-origin xavfi (brauzer mehmoni oxirgi Telegram foydalanuvchisi identity'sini olishi)
allaqachon yopilgan: localStorage tiklash faqat `inTelegram` bo'lganda ishlaydi, brauzerда
`platform=unknown` → tiklash yo'q. Bu D'да qayta hal qilinmadi.

## Tekshiruv

Plain brauzerда (initData yo'q — haqiqiy ommaviy yo'l): `/kitoblar/` → kitob → unit → reader
(1/3→2/3→3/3 varaqlash, oxirgi sahifада next disabled), so'z kartalari + rasm/ipa/ta'rif/misol
render, "Bugun"/"Profil" yashirin, "Kitoblar"/"Mashqlar" ochiq, data endpointlar 200, landing
havolasi `/kitoblar/` ga. (Lokal `app.css` 404 — Docker'да build bo'ladi, prod'да bor.)
