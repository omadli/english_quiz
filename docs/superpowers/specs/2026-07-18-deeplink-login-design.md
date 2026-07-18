# Deep-link web login (B)

**Sana:** 2026-07-18 · **Holat:** tasdiqlangan (savol-javobda "to'liq almashtirish")

## Muammo

Hozirgi `/login/`: foydalanuvchi `@username` kiritadi → server `resolve_account` bilan
Telegram akkauntini topadi → Django jarayonidan sinxron `requests.post` bilan kod DM qiladi.
Ikki kamchilik: (1) `@username` kiritish noqulay va `api_request_code` **username
enumeration oracle** (`not_found` ni `throttled` dan farqli qaytaradi, per-IP throttle yo'q);
(2) kod yuborish web so'rovini 10s gacha bloklaydi.

## Yechim — deeplink + bir martalik kod

`/login/` da bitta tugma: **"Telegram orqali kod olish →"**. Bosilganda:

1. Frontend `POST /app/api/login-link/` → server `nonce` (token_urlsafe) yaratadi, 10 daqiqa
   TTL, `{nonce, url}` qaytaradi. `url = t.me/<bot>?start=login_<nonce>`.
2. Frontend deeplink'ni ochadi (`window.open`/`location`), va kod kiritish qadamiga o'tadi
   (`nonce` ni JS o'zgaruvchisида saqlaydi).
3. Foydalanuvchi botда `start` bosadi → bot `login_<nonce>` ni ko'radi → nonce'ga o'sha
   foydalanuvchini biriktiradi, 6 xonali kod yaratadi, **bot jarayonidan** DM qiladi.
4. Foydalanuvchi kodni botда oladi, saytga qaytib kiritadi → `POST /app/api/verify-code/`
   `{nonce, code}` → login.

Kimligini tasdiqlash `start` bosган Telegram foydalanuvchisidан keladi (bot uni biladi),
ya'ни `@username` kiritish umuman kerak emas — enumeration oracle yo'qoladi.

## Model — `LoginCode` ni qayta ishlatish

Yangi model qo'shmaymiz; mavjud `LoginCode` ni nonce oqimiga moslaymiz (u faqat login.py da
ishlatiladi):

- `nonce = CharField(max_length=48, unique=True)` — brauzer sessiyasi tokeni (yangi).
- `user` → **nullable** (deeplink ochilгунча noma'lum).
- `code` → **blank** (deeplink ochilгунда to'ldiriladi).
- `expires_at`, `attempts`, `used` — o'zгармайди.

Migratsия: `nonce` qo'shish, `user` null=True, `code` blank=True.

## Service — `apps/accounts/services/login.py` qayta yoziladi

O'chadi: `resolve_account`, `request_login_code`, `_send_code_dm` (sinxron `requests.post`),
`verify_login_code(identifier, code)`.

Qo'shiladi:
- `create_login_request() -> str` — nonce yaratadi, qaytaradi.
- `fulfill_login_request(nonce, user) -> str | None` — bot tomoni: nonce'ni topadi (used
  emas, muddati o'tмаган), user + 6 xonali kod biriktiradi, kodni qaytaradi (bot DM qiladi).
  Nonce topilmаса `None`.
- `verify_login_request(nonce, code) -> User | None` — nonce'ни topadi, `attempts`/`used`
  cheklовлари (mavjudдек: MAX_ATTEMPTS=5, constant-time compare), muvaffaqiyатда `used=True`
  va faol user qaytaradi.

`requests` import va Django'dagi DM logikаси butunlay o'chadi.

## Bot — `bot/handlers/start.py`

Mavjud `login_quiz`/`g<token>` tarmoqlari yonида (start.py allaqачon conftest'да ro'yxatда —
yangi handler fayl yo'q):

```python
if payload.startswith("login_"):
    code = await sync_to_async(fulfill_login_request)(payload[len("login_"):], user)
    await message.answer(strings.LOGIN_CODE.format(code=code) if code else strings.LOGIN_LINK_EXPIRED)
    return  # login uchun kelди — onboarding'ga tushмайди
```

`strings.py`: `LOGIN_CODE` ("🔐 Kirish kodingiz: <b>{code}</b> ..."), `LOGIN_LINK_EXPIRED`.

## Views — `apps/accounts/views.py`

- `api_request_code` → **`api_login_link`** (`POST` → `{ok, nonce, url}`; `settings.BOT_USERNAME`
  bo'sh bo'lsa `{ok: False, error: "no_bot"}`).
- `api_verify_code` → body endi `{nonce, code}` (identifier emas) → `verify_login_request`.
- URL: `/app/api/request-code/` → `/app/api/login-link/`.

## Template — `templates/web/login.html`

`@username` input o'chadi. Bitta tugма → login-link oladi → deeplink ochadi → kod qadami.
Kod input → `{nonce, code}`. Telegram-ichи initData avto-login (mavjud) o'zгармайди.

## Xavfsizlik

- Nonce `secrets.token_urlsafe(24)` — taxmin qilib bo'lmaydi.
- Kod hali ham 6 xonali, MAX_ATTEMPTS=5, constant-time.
- Enumeration oracle yo'qoladi (username kiritilmaydi).
- Muddати o'тган nonce'lar keyingi `create_login_request` да tozalanмайди — TTL DB filtrда;
  hajm kichик, cleanup task qo'шMaymiz (ponytail — kerak bo'lса keyin).

## Tekshiruv

- `create_login_request` nonce yaratadi; `fulfill` user+kod biriktiradi; `verify` to'g'ri
  kodда user qaytaradi, noto'g'рида `attempts++`, capда `used`, muddати o'тганда `None`.
- View: `login-link` `{nonce, url}` qaytaradi; `verify-code` `{nonce, code}` bilan login qiladi.
- Bot: `login_<nonce>` start → kod DM, onboarding'ga tushмайди.
- Prod: `/login/` da tugма bosib, botда kod olib, saytga kirib ko'rish.
