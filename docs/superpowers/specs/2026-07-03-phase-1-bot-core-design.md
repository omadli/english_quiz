# Faza 1 — Bot yadrosi (Bot Core) — Dizayn Spec

**Sana:** 2026-07-03
**Faza:** 1 / 6 (`product-vision-and-roadmap.md` ga qarang)
**Holat:** Tasdiqlash kutilmoqda
**Tayanadi:** Faza 0 (poydevor) — tugallangan, `main`'da.

---

## 1. Maqsad va natija

aiogram 3.x asosidagi Telegram bot yadrosini qurish: foydalanuvchini ro'yxatdan o'tkazadi, tanishtiradi va **sozlamalar sehrgari** orqali o'quv rejasini (kunlik maqsad, jadval, vaqtlar, audio) sozlaydi. Sozlamalar Django bazasida saqlanadi va istalgan vaqt `/settings` orqali tahrirlanadi.

Faza oxirida:
- `docker compose up bot` — bot ulanadi va `/start`'ga javob beradi.
- Yangi foydalanuvchi `/start` → `User` + `TelegramAccount` + `LearningProfile` yaratiladi, onboarding o'tadi, sozlamalar saqlanadi.
- `/settings` — joriy sozlamalarni ko'rsatadi va tahrirlaydi.
- Qayta `/start` dublikat yaratmaydi; qaytgan foydalanuvchi kutib olinadi.
- Service qatlami va yordamchilar uchun testlar o'tadi.

**Bu fazada YO'Q (keyingi fazalarda):** kunlik so'z yuborish, imtihon, Celery jadvali (Faza 2); motivatsion nudge, ota-ona/ustoz rejimi, PDF (Faza 4); guruh quiz (Faza 3); web (Faza 5).

---

## 2. Texnologiya va qarorlar

| Mavzu | Qaror |
|-------|-------|
| Bot framework | **aiogram 3.x** (Faza 0'da `pyproject`' da e'lon qilingan) |
| Django integratsiya | Bot alohida jarayon; `django.setup()` chaqiradi va **Django ORM**'ni to'g'ridan-to'g'ri ishlatadi (alohida API yo'q). Service qatlami **sync** ORM funksiyalari; handler/middleware ularni `asgiref.sync.sync_to_async` bilan chaqiradi. *(Sabab: native async ORM test-tranzaksiya va bog'liq-obyekt kirishida nozik; sync + `sync_to_async` ishonchli va oson testlanadi.)* |
| FSM storage | **aiogram `RedisStorage`** (Redis DB 2 — cache DB1/celery DB0'dan ajratilgan) |
| Ulanish | **Long polling** (`dp.start_polling`) — Docker'da public URL kerak emas. Webhook keyingi (prod) uchun qoldiriladi. |
| Til | O'zbekcha; barcha matn `bot/strings.py` da (i18n-ready, keyin `aiogram.utils.i18n`) |
| Onboarding | Sehrgar, **"Standart bilan boshlash"** bilan o'tkazib bo'ladigan |
| Jadval | Hafta kunlari tanlash + seansdagi so'z soni |
| Telefon | Onboarding'da so'ralmaydi (telegram_id yetarli; keyin ixtiyoriy) |
| Timezone | `Asia/Tashkent` (hozircha qat'iy; so'ralmaydi) |

---

## 3. Ma'lumot modeli — yangi `apps/learning`

`apps/learning/` (label `learning`, `INSTALLED_APPS`'ga qo'shiladi).

### `LearningProfile(TimeStampedModel)`
| Maydon | Tur | Standart | Izoh |
|--------|-----|----------|------|
| `user` | OneToOne→accounts.User, related_name="learning_profile" | | |
| `words_per_session` | PositiveSmallInt | 10 | Har seansdagi yangi so'zlar soni |
| `study_weekdays` | JSONField (list[int]) | `[0,1,2,3,4,5,6]` | 0=Dushanba … 6=Yakshanba |
| `morning_time` | TimeField | 07:00 | Ertalabki so'z yuborish vaqti (Faza 2) |
| `exam_time` | TimeField | 20:00 | Kechki imtihon vaqti (Faza 2) |
| `audio_enabled` | Bool | True | Audio yuborilsinmi |
| `audio_repeat` | PositiveSmallInt | 2 | Talaffuz+tarjima necha marta o'qilsin |
| `timezone` | Char(40) | "Asia/Tashkent" | |
| `language` | Char(8) | "uz" | |
| `onboarded` | Bool | False | Onboarding tugallanganmi |
| `is_active` | Bool | True | O'quv faol/pauza |
| `current_book` | FK→catalog.Book, null | | Joriy kitob (onboarding'da 1-kitob) |
| `current_unit` | FK→catalog.Unit, null | | Joriy unit (pozitsiya anchor'i, Faza 2 ishlatadi) |
| `current_word_order` | PositiveSmallInt | 0 | Unit ichidagi oxirgi yuborilgan tartib |

- `study_weekdays` uchun modul-darajali `default_weekdays()` funksiyasi `[0,1,2,3,4,5,6]` qaytaradi (mutable-default tuzog'idan qochish).
- **Bir foydalanuvchi = bitta faol kurs** (YAGNI). Ko'p kitob kerak bo'lsa keyin `Enrollment` modeliga refaktor. Pozitsiya profilda saqlanadi.
- Helper metodlar: `studies_today(weekday) -> bool`, va admin uchun `__str__`.

`apps/learning/admin.py` — unfold `ModelAdmin` bilan `LearningProfile` (user, words_per_session, onboarded, is_active).

---

## 4. Bot tuzilishi (`bot/` paketi)

Faza 0'dagi stub (`bot/__main__.py` sleep) haqiqiy dispatcher bilan almashtiriladi.

```
bot/
  __init__.py
  __main__.py            # entrypoint: django.setup → Bot, Dispatcher(RedisStorage), routerlar, start_polling
  config.py              # settings'dan BOT_TOKEN, REDIS_URL (DB2) o'qish + xatolik agar token yo'q
  strings.py             # o'zbekcha matn konstantalari (i18n-ready)
  keyboards/
    __init__.py
    onboarding.py        # sehrgar qadamlari uchun inline keyboardlar
    settings.py          # sozlamalar menyusi keyboardlari
    common.py            # umumiy (Skip, Cancel, Back, Tayyor)
  states/
    __init__.py
    onboarding.py        # OnboardingStates(StatesGroup)
  handlers/
    __init__.py
    start.py             # /start, ro'yxatdan o'tish, sehrgarga kirish
    onboarding.py        # sehrgar qadamlari (FSM)
    settings.py          # /settings ko'rish + tahrirlash
    common.py            # /cancel, /help, fallback + global error handler
  services/
    __init__.py
    users.py             # get_or_create_user, profil o'qish/yozish (async ORM)
  middlewares/
    __init__.py
    user.py              # handler data'siga (user, profile) ni inject qilish
```

**Har fayl bitta mas'uliyat.** Handlerlar yupqa — biznes/DB mantiq `services/`da; matn `strings.py`da; tugmalar `keyboards/`da.

### Django integratsiya (`bot/__main__.py`)
1. `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")` → `django.setup()`.
2. Modellarni `django.setup()` **dan keyin** import qilish.
3. `Bot(token=settings.BOT_TOKEN)`, `Dispatcher(storage=RedisStorage.from_url(<redis DB2>))`.
4. Routerlarni ulash (start, onboarding, settings, common), UserMiddleware'ni ulash.
5. `await dp.start_polling(bot)`.

### Service qatlami (`bot/services/users.py`) — **sync** funksiyalar (handler `sync_to_async` bilan chaqiradi)
- `get_or_create_user(telegram_id, username, first_name, last_name, language_code) -> tuple[User, LearningProfile, bool]` — telegram_id bo'yicha `TelegramAccount`'ni topadi yoki `User`+`TelegramAccount`+`LearningProfile` yaratadi (idempotent). `created` qaytaradi. TG profil ma'lumotlarini yangilaydi. (Oddiy argumentlar — aiogram tiplariga bog'liq emas, oson testlanadi.)
- `update_profile(profile, **fields)` — sozlamalarni saqlash.
- `set_starting_position(profile)` — `current_book`=birinchi faol Book, `current_unit`=uning birinchi unit'i, `current_word_order`=0.
- `apply_wizard_data(profile, data: dict)` — sehrgar to'plagan ma'lumotni profil maydonlariga o'giradi va saqlaydi (onboarded=True + starting position).

---

## 5. Onboarding oqimi (FSM)

1. **`/start`:**
   - `get_or_create_user`.
   - `onboarded=True` bo'lsa → xush kelibsiz + asosiy menyu (hozircha: qisqa holat + `/settings`).
   - Yangi/onboard qilinmagan bo'lsa → tanishtirish xabari + ikki tugma: **"Sozlashni boshlash"** va **"Standart bilan boshlash"**.
2. **Sehrgar qadamlari** (har biri FSM state + inline keyboard):
   - `WORDS_PER_SESSION`: 5 / 10 / 15 / 20 / boshqa (custom raqam).
   - `STUDY_WEEKDAYS`: Du–Ya toggle (multi-select) + "Har kuni" + "Tayyor".
   - `MORNING_TIME`: tayyor variantlar (06:00/07:00/08:00) yoki custom `HH:MM`.
   - `EXAM_TIME`: tayyor (19:00/20:00/21:00) yoki custom `HH:MM`.
   - `AUDIO`: yoqilsinmi (Ha/Yo'q) → yoqilsa takror (1/2/3).
   - `CONFIRM`: xulosa (barcha sozlama) → "Saqlash" → `onboarded=True`, `set_starting_position`, tabrik.
3. **"Standart bilan boshlash"** → standart qiymatlar, `onboarded=True`, `set_starting_position`, tayyor.
4. **`/settings`** → joriy sozlamalarni ko'rsatadi, har biri yonida tahrir tugmasi → bitta maydonni tahrirlash sehrgar qadamini qayta ishlatadi (bitta-maydon rejimi).

### Vaqt kiritish
Umumiy vaqtlar uchun tayyor tugmalar; "custom" `HH:MM` matnini so'raydi, `datetime.time`'ga parslaydi/validatsiya qiladi, xato bo'lsa qayta so'raydi.

---

## 6. Xatoliklarni boshqarish

- Dispatcher'da **global error handler**: log + foydalanuvchiga "Xatolik yuz berdi, qayta urinib ko'ring" xabari.
- Vaqt/raqam kiritish validatsiyasi; noto'g'ri bo'lsa qayta so'rash.
- `config.py`: `BOT_TOKEN` bo'sh bo'lsa aniq xatolik bilan to'xtaydi (lekin service/testlar token'siz ishlaydi — Bot yaratish faqat `__main__`'da).
- Foydalanuvchi botni bloklasa (Faza 2 yuborishda muhim) — hozircha oddiy handle; `TelegramAccount.blocked_bot` keyin ishlatiladi.

---

## 7. Testlar (pytest + pytest-django)

- **Service:** `get_or_create_user` idempotentligi (ikki marta chaqirilsa dublikat yaratmaydi, TG maydonlarini yangilaydi); `update_profile`; `set_starting_position` (1-kitob/1-unit tanlanishi).
- **Yordamchilar:** weekday parse/format, `HH:MM` vaqt validatsiyasi (to'g'ri/noto'g'ri), keyboard builderlar (kutilgan tugma matni/callback_data).
- **FSM/handler (yengil):** `mock`langan Bot/Message bilan bir-ikki smoke-test — `/start` yangi foydalanuvchi uchun onboarding boshlashini va "Standart bilan boshlash" `onboarded=True` qilishini tekshiradi.
- Testlar real `BOT_TOKEN` talab qilmaydi (dummy). Aiogram versiyasiga mos test yondashuvi implementatsiya rejasida aniqlanadi.
- Test chiqishi toza (pristine).

---

## 8. Konfiguratsiya

- `BOT_TOKEN` — env (`.env`, Faza 0'da mavjud). Haqiqiy token foydalanuvchi tomonidan beriladi (BotFather).
- Redis FSM: `REDIS_URL`'dan DB 2 (`.../2`). `.env.example`'ga izoh qo'shiladi.
- `compose.yaml` `bot` xizmati allaqachon `python -m bot` ni ishga tushiradi (Faza 0). Endi u haqiqiy botni ishga tushiradi.

---

## 9. Muvaffaqiyat mezoni (Definition of Done)

- [ ] `apps/learning` — `LearningProfile` modeli + migratsiya + unfold admin.
- [ ] `bot/` — dispatcher, routerlar, service, middleware, strings, keyboards, states.
- [ ] `/start` yangi foydalanuvchini ro'yxatdan o'tkazadi va onboarding boshlaydi; "Standart bilan boshlash" ishlaydi.
- [ ] Sehrgar barcha sozlamani to'playdi va saqlaydi; `/settings` ko'rsatadi va tahrirlaydi.
- [ ] Qayta `/start` idempotent.
- [ ] `docker compose up bot` — bot ulanadi (real token bilan) va `/start`'ga javob beradi.
- [ ] Testlar yashil, `ruff` toza.

---

## 10. Ochiq savollar / xavflar

- **Handler test chuqurligi:** aiogram 3.x uchun to'liq handler integratsiya testi og'ir; asosiy qamrov service+yordamchilarda, handlerlarda yengil smoke-test. Implementatsiya rejasi aniq test yondashuvini belgilaydi.
- **Real BOT_TOKEN:** `docker compose up bot` bilan uchidan-uchiga tekshiruv foydalanuvchidan BotFather token'ini talab qiladi; usiz kod/testlar baribir to'liq tekshiriladi.
- **Timezone:** hozircha qat'iy Asia/Tashkent; ko'p timezone kerak bo'lsa keyin sozlama qo'shiladi (jadval Faza 2'da timezone'ni hisobga oladi).
