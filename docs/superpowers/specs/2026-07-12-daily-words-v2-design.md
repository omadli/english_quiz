# Kunlik So'zlar Tajribasi v2 (Daily Words v2) — Dizayn Spec

**Sana:** 2026-07-12
**Sub-project:** ① (uch bo'limdan biri; ② Vasiy boshqaruvi, ③ Hisobotlar — alohida spec'lar)
**Holat:** Foydalanuvchi dizaynni tasdiqladi ("go") — spec yozildi
**Tayanadi:** Faza 0–5 `main`'da, PROD LIVE (webhook). Mavjud: `LearningProfile`, `DailySession`/`SessionWord`, `run_delivery`, `build_word_audio`, pluggable `TTS_PROVIDER` (gTTS), `bot.sender.send_daily`, Mini App SPA (`templates/webapp/index.html`) + `apps/catalog/views.py` JSON API (`_profile_from_request` initData auth, word serializatsiya).

---

## 1. Maqsad va natija

Kunlik so'z o'rganish tajribasini yaxshilash: klaviatura polish, tushunarli sozlamalar, **tekin multi-voice TTS (edge-tts)**, va ertalabki yuborishni **bitta xabar + bitta audio** ko'rinishiga o'tkazish; Mini App'da "Bugungi so'zlar" bo'limi.

Faza oxirida:
- Menu reply keyboard `one_time` (ekranni doim egallamaydi); "Guruh quizi" + "Reyting" tugmalari yo'q.
- Sozlamalarda har band joriy qiymati bilan; **EN/UZ ovoz** va **takror** tanlanadi (bot + Mini App).
- Ertalab: **bitta audio** (har so'z `EN×takror → UZ`) + izohida so'zlar ro'yxati + inline **📖 Batafsil** (Mini App `?view=today`). Rasmsiz.
- Mini App'da "Bugungi so'zlar" — bugungi `DailySession` so'zlari unit kartalaridek (rasm, izoh, misol, ovoz).
- Testlar o'tadi, `ruff` toza.

---

## 2. Qarorlar

| Mavzu | Qaror |
|-------|-------|
| Klaviatura | `is_persistent` olib tashlanadi, `one_time_keyboard=True`. "Guruh quizi"/"Reyting" olib tashlanadi |
| TTS engine | Yangi `EdgeTTSProvider` (edge-tts, tekin, API key yo'q). `TTS_PROVIDER` orqali plugin. Prod `.env` = Edge; lokal default gTTS qoladi |
| TTS interfeys | `synthesize(text, lang="en", voice: str \| None = None)` — mavjud `GTTSProvider` `voice`'ни e'tiborsiz qoldiradi |
| Ovozlar | EN: kichik ro'yxat (Aria/Jenny ayol, Guy/Christopher erkak, +en-GB). UZ: **faqat 2** — Madina (ayol, default), Sardor (erkak). Edge-tts'da boshqa UZ ovozi yo'q |
| Fallback | Audio builder configured provider'ni sinaydi; xatoda EN→gTTS, UZ→tashlab ketiladi (audio EN-only) |
| Yangi dep | `edge-tts` (pyproject + uv.lock; Docker rebuild) |
| Data model | `LearningProfile.en_voice`, `.uz_voice` (CharField); `audio_repeat` semantikasi o'zgaradi (EN takrorlanadi, UZ 1 marta). Migration: `learning` |
| Audio v2 | `build_daily_audio(words, en_voice, uz_voice, repeat)` → bitta MP3. Per-so'z bitta-ovozli segmentlar keshlanadi (word+lang+voice); kunlik konkatenatsiya on-the-fly |
| Xabar v2 | Bitta `send_audio` (caption=ro'yxat, inline Batafsil). Caption >1024 → ro'yxat alohida matn, audio qisqa caption bilan |
| Batafsil | inline `web_app` tugma → `WEBAPP_URL` + `?view=today` (faqat `WEBAPP_URL` bo'lsa) |
| Mini App today | `/webapp/api/today/` (initData auth) + SPA `?view=today` ekrani; mavjud so'z-karta komponenti qayta ishlatiladi |
| Onboarding | Ovoz qadami QO'SHILMAYDI (default'lar; sozlamalarda o'zgartiriladi) |

---

## 3. Ma'lumot modeli o'zgarishi

`LearningProfile` (yangi maydonlar, migration `learning/000X`):
- `en_voice = CharField(max_length=40, default="en-US-AriaNeural")`
- `uz_voice = CharField(max_length=40, default="uz-UZ-MadinaNeural")`

`audio_repeat` (mavjud, default 2) — endi **faqat EN qismini** N marta takrorlaydi, UZ 1 marta. Model o'zgarmaydi, faqat `audio.py` ishlatishi.

Boshqa yangi model yo'q. `DailySession`/`SessionWord` o'zgarmaydi (imtihon oqimi buzilmaydi — `SessionWord` avvalgidek yaratiladi).

---

## 4. Komponentlar

### 4.1 Menu (`bot/keyboards/menu.py`)
`main_menu_keyboard`: qatorlar Bugungi vazifa · Imtihon / Test · So'zlar / Kitoblar · Sozlamalar (+ Mini App). `MENU_GROUP_QUIZ`, `MENU_TOP` tugmalari olib tashlanadi (strings qoladi — boshqa joyda ishlatilishi mumkin). `ReplyKeyboardMarkup(..., resize_keyboard=True, one_time_keyboard=True)` (`is_persistent` yo'q).

### 4.2 TTS (`apps/common/tts.py`)
- `TTSProvider.synthesize(text, lang="en", voice=None)`.
- `EdgeTTSProvider`: `edge_tts.Communicate(text, voice or _default(lang)).stream()` orqali MP3 bytes yig'adi; `asyncio.run` bilan sync qobiq (Celery worker'da running loop yo'q). Xatoda `raise`.
- Katalog konstantalari: `EN_VOICES: list[tuple[id,label]]`, `UZ_VOICES = [("uz-UZ-MadinaNeural","Madina (ayol)"), ("uz-UZ-SardorNeural","Sardor (erkak)")]`, `_DEFAULTS`.
- `get_tts_provider()` o'zgarmaydi.

### 4.3 Sozlamalar (`bot/keyboards/settings.py`, `bot/handlers/settings.py`, `bot/strings.py`)
- `settings_keyboard(profile)` — har tugmada joriy qiymat (masalan `🔤 So'z soni: 10`, `🇬🇧 Ingliz ovozi: Aria`, `🇺🇿 O'zbek ovozi: Madina`, `🔁 Takror: 2`).
- Yangi callback'lar: `set:envoice` → EN ovoz ro'yxati (`set:envoice:<id>`); `set:uzvoice` → UZ ro'yxati; `set:repeat` → 1/2/3 tanlash. Tanlangach saqlaydi va sozlamalar ekranini yangilaydi.
- `format_profile` ovozlar + takrorni ko'rsatadi.

### 4.4 Ertalabki yuborish v2 (`apps/learning/services/audio.py`, `deliver.py`, `bot/sender.py`)
- `audio.py`: `build_daily_audio(words, en_voice, uz_voice, repeat) -> bytes`. Har so'z: `en_seg*repeat` + 300ms + `uz_seg`; so'zlar orasi 700ms. Per-segment kesh: `media/audio/seg/<lang>/<voice>/<word>.mp3`. `_synth(text, lang, voice)` — configured provider, xatoda gTTS fallback (EN) / None (UZ). Eski `build_word_audio` olib tashlanadi/almashtiriladi.
- `deliver.py`: `run_delivery` — endi bitta caption (ro'yxat) + bitta audio quradi; `SessionWord`/`WordProgress` avvalgidek; rasm/`render_daily_card` yo'q. `today_session_items` → `today_session_payload` (caption+audio). `_caption` → `_word_list_caption(words)` (`1. word [IPA] — uz`, `part_of_speech` ixtiyoriy).
- `sender.py`: `send_daily(chat_id, caption, audio, webapp_url)` — `send_audio(audio, caption=..., reply_markup=inline[📖 Batafsil web_app])`; caption>1024 → oldin `send_message(ro'yxat)`, keyin audio qisqa caption. `webapp_url` bo'lmasa tugma yo'q.
- `cards.py` (`render_daily_card`) endi ishlatilmaydi → olib tashlanadi (faqat shu joyda ishlatilardi).

### 4.5 Mini App "Bugungi so'zlar" (`apps/catalog/views.py`, `config/urls.py`, `templates/webapp/index.html`)
- `api_today(request)` — `@csrf_exempt`, `_profile_from_request` (initData) → `today_session_words(profile.user_id)` (import `apps.learning.services.deliver`) → mavjud so'z serializatsiyasi bilan JSON (`api_words` bilan bir xil shakl). Sessiya yo'q → `{"words": []}`. Route `webapp/api/today/`.
- SPA: yuklanишda `?view=today` bo'lsa "Bugungi so'zlar" ekrani — mavjud so'z-karta renderer'i (unit words) qayta ishlatiladi; `getJSON('/webapp/api/today/')` (initData header). Bo'sh bo'lsa "Bugun uchun so'z yo'q" hint. (Faqat kompilyatsiya qilingan Tailwind klasslardan foydalanamiz — CSS rebuild kerak emas.)

---

## 5. Testlar (TDD)

- `apps/common/tests/test_tts.py` — `EdgeTTSProvider` `voice` param'ni uzatadi (edge_tts mock); default lang→voice.
- `apps/learning/tests/test_audio.py` — `build_daily_audio` tuzilishi (EN×repeat + UZ; TTS mock), segment kesh (2-chi chaqiruv synth chaqirmaydi), fallback (Edge xato → gTTS).
- `apps/learning/tests/test_deliver.py` — `run_delivery` bitta audio + ro'yxat-caption + Batafsil tugma yuboradi (sender mock), rasm yo'q; `SessionWord` yaratiladi; caption>1024 tarmoqlanishi.
- `apps/catalog/tests/test_webapp_today.py` — `/webapp/api/today/`: auth yo'q→401, sessiya yo'q→bo'sh, bor→bugungi so'zlar.
- Bot keyboard/handler testlari — menu (tugmalar yo'q, one_time), settings (ovoz/takror pickerlari saqlaydi).

---

## 6. Bu sub-project'da YO'Q

- Vasiy (ota-ona/o'qituvchi) boshqaruvi va har-o'quvchi sozlamalari → **sub-project ②**.
- O'quvchi dashboard/hisobotlari (yodlangan/xato so'zlar, bajarilmagan kunlar) → **sub-project ③**.
- Onboarding'ga ovoz qadami; ertalabki xabarda per-so'z rasm; UZ uchun 3-ovoz (edge-tts'da yo'q).

---

## 7. Risklar / eslatmalar

- **edge-tts tarmoqqa bog'liq** (Microsoft edu endpoint). Celery worker'da tarmoq bor. Rate-limit'ni per-segment kesh yumshatadi; xatoda gTTS fallback.
- **Yangi dep** → Docker image rebuild (CI avtomatik). `uv.lock` yangilanadi.
- **Prod bot webhook** — bot o'zgarishlarini lokal jonli bot bilan test qilib bo'lmaydi (lokal polling prod webhook'ni o'chiradi). Test = `pytest`; jonli tekshiruv deploy'dan keyin yoki alohida dev token bilan.
- Prod `.env` ga `TTS_PROVIDER=apps.common.tts.EdgeTTSProvider` qo'shiladi (deploy paytida).
