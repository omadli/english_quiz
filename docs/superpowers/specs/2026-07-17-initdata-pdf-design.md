# initData persistence + PDF delivery (Mini App)

**Sana:** 2026-07-17
**Holat:** tasdiqlangan, implementatsiyaga tayyor

## Dastur konteksti (dekompozitsiya)

2026-07-17 brain-dump'i beshta ishni o'z ichiga oldi. Ular mustaqil, har biri alohida
spec → plan → deploy oladi. Ushbu spec faqat **A** ni qamraydi.

| # | Ish | Holat |
|---|-----|-------|
| **A** | initData navigatsiyada yo'qolishi + PDF (botga yuborish + yuklash) | **shu spec** |
| B | Deeplink login (`t.me/bot?start=login_<nonce>` → bir martalik kod) | keyingi spec |
| C | Qarzdorlik imtihoni (`MISSED` status + ertangi oxirgi imkoniyat) | keyingi spec |
| D | Ommaviy kitob reader (SPA reader rejimi, `/kitoblar/`) | keyingi spec |

A birinchi: prod'da tirik bug, va PDF havolasi o'sha bug'ning eng ehtimolli sababi —
ikkalasi bitta kod yo'lida.

## Muammo

**Simptom (foydalanuvchi hisoboti):** Mini App'da navigatsiya orqali orqaga qaytilganda
foydalanuvchi ma'lumotlari topilmaydi, "bugungi vazifalar yo'q" deydi, sozlamalar ishlamaydi
— ya'ni initData'ga tayangan hamma endpoint 401 qaytaradi.

**Nima sabab emas.** Oddiy reload sabab emas: `telegram-web-app.js` initParams'ni
`sessionStorage`ga (`__telegram__initParams`) yozadi va hash bo'lmaganda o'shandan tiklaydi
(skript boshidagi IIFE). Ya'ni bir kontekst ichidagi qayta yuklash initData'ni saqlaydi.

**Eng ehtimolli sabab.** `templates/webapp/index.html:300` — PDF havolasi:

```html
<a href="${book.pdf}" target="_blank" rel="noopener">📥 PDF</a>
```

Bu `/media/books/pdf/<file>.pdf` ga to'g'ridan-to'g'ri, **o'sha origin** ichida navigatsiya.
Telegram in-app webview `target="_blank"` ni har doim hurmat qilmaydi; PDF ochilib, orqaga
qaytilganda Mini App yangi webview kontekstida qayta yuklanadi — yangi kontekst = bo'sh
`sessionStorage` = initData yo'q. Bu SPA ichidagi yagona sahifadan chiqib ketuvchi havola
(`location`/`history` manipulyatsiyasi kodda yo'q — tasdiqlangan).

Bu gipoteza to'liq tasdiqlanmagan (prod'dan real repro olinmadi), shuning uchun tuzatish
sababdan qat'i nazar ishlashi kerak: initData'ni o'zimiz saqlaymiz.

## Yechim

### A1 — initData'ni localStorage'da saqlash

`templates/webapp/index.html` skript boshida:

- `tg.initData` bo'lsa → `localStorage`ga yoziladi.
- Bo'sh bo'lsa → `localStorage`dan tiklanadi.

`sessionStorage` emas, `localStorage`: sessionStorage kontekst almashuvida yo'qoladi, aynan
shu buzilayotgan holat. Telegram'ning o'z sessionStorage tiklashi bor — ya'ni bizniki faqat
u yetmagan holatda ishga tushadi.

**Xavfsizlik cheklovi (majburiy):** tiklash **faqat Telegram ichida** bajariladi —
`tg.platform && tg.platform !== "unknown"`. Sabab: D ishida SPA aynan shu origin'da
ommaviy bo'ladi; cheklovsiz brauzerda begona odam `/webapp/` ni ochib, oxirgi Telegram
foydalanuvchisining saqlangan initData'si bilan uning profiliga kirib qolardi. Telegram
tashqarisida saqlash ham, tiklash ham yo'q.

Eskirgan initData server'da rad etiladi — `parse_init_data` allaqachon 24 soatlik
`_INIT_DATA_MAX_AGE` ni tekshiradi (`apps/common/webapp_auth.py`). Ya'ni saqlangan qiymat
xavfsizlik oynasini kengaytirmaydi; u faqat mavjud oyna ichida ishlaydi.

Akkaunt almashuvi xavfsiz: `tg.initData` bo'lgan har safar ustiga yoziladi, tiklash faqat
u bo'sh bo'lgandagina.

### A2 — PDF: botga yuborish + faylni yuklash

**Backend.** Yangi `POST /webapp/api/send-pdf/<book_id>/`, initData auth
(`_profile_from_request`, boshqa `/webapp/api/` authed endpoint'lari bilan bir xil).
Mavjud yo'lni qayta ishlatadi, yangi yuborish logikasi yozilmaydi:

- `apps/learning/services/book_pdf.get_sendable_book(book_id)` → `(filename, payload)`,
  payload = cache'langan `Book.telegram_file_id` (str) yoki xom baytlar.
- `bot/sender.send_document(chat_id, payload, filename)` → `file_id` qaytaradi.
- Birinchi yuborishda `book_pdf.save_file_id(book_id, file_id)` — keyingilari qayta
  yuklanmaydi.

Javob: `{"ok": true}`. Xatolar: auth yo'q → 401, kitob yo'q / PDF yo'q → 404,
Telegram rad etsa (bloklangan) → 502 + `{"ok": false}`.

`is_active=False` kitoblar filtrlanadi — bot tomonidagi `send_pdf` da yo'q bo'lgan tekshiruv
(`bot/handlers/books.py:36` faqat pk bo'yicha qidiradi). Yangi endpoint ommaviy callback
qabul qilgani uchun bu yerda shart.

**Frontend.** `<a href target="_blank">` o'chadi, o'rniga tugma:

1. `POST send-pdf/` → muvaffaqiyatda tugma matni "✅ Botga yubordim" ga o'zgaradi.
2. Parallel: `tg.downloadFile({url, file_name})` (Bot API 8.0+); mavjud bo'lmasa
   `tg.openLink(url)`. Ikkalasi ham sahifadan chiqib ketmaydi — initData saqlanadi.
3. Telegram tashqarisida (brauzer, D ishidan keyin): bot chaqirilmaydi, tugma oddiy
   `<a download>` havolasi bo'lib qoladi.

## Nima o'zgarmaydi

- `Book.telegram_file_id` cache sxemasi va `book_pdf` xizmati — qayta ishlatiladi.
- Bot'dagi "📚 Kitoblar" → PDF yo'li — tegilmaydi.
- `/media/` ommaviyligi — PDF URL'lari hozir ham auth'siz (nginx serve qiladi). Buni
  yopish alohida ish; bu spec uni o'zgartirmaydi va yomonlashtirmaydi.
- `parse_init_data` va 24 soatlik oyna.

## Tekshiruv

- `send-pdf`: initData'siz → 401 (mavjud auth testlari qolipida).
- `send-pdf`: cache'langan `telegram_file_id` bo'lsa qayta yuklanmaydi (sender mock'lanadi,
  `send_document` argumenti str ekani tasdiqlanadi); cache bo'sh bo'lsa baytlar yuboriladi
  va qaytgan `file_id` saqlanadi.
- `send-pdf`: `is_active=False` kitob → 404.
- initData saqlash — JS, avtomatlashtirilgan test yo'q; prod'da qo'lda: Mini App → PDF →
  orqaga → Sozlamalar ochilishi kerak.

## Ochiq risk

initData yo'qolishining sababi PDF havolasi emas, boshqa narsa bo'lishi mumkin (prod'dan
real repro olinmadi). A1 sababdan qat'i nazar ishlaydi, lekin agar deploy'dan keyin ham
takrorlansa — keyingi gumondor: Telegram klientining webview'ni butunlay yangi origin
kontekstida qayta ochishi, u holda `localStorage` ham bo'sh bo'ladi va yagona yechim
har bir so'rovda serverga cookie sessiyasi qo'yish bo'ladi (A dan tashqarida).
