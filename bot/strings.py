# Uzbek UI text. Handlers reference these constants; no inline literals elsewhere.

WELCOME_NEW = (
    "Assalomu alaykum! 👋\n\n"
    "Men <b>4000 Essential Words</b> so'zlarini yodlashda shaxsiy mentoringizman.\n"
    "Har kuni belgilangan vaqtda yangi so'zlarni yuboraman va imtihon qilaman.\n\n"
    "Keling, avval o'quv rejangizni sozlaymiz."
)
WELCOME_BACK = "Xush kelibsiz! 👋✨ Quyidagi menyudan foydalaning 👇"
LINKED_OK = "✅ Muvaffaqiyatli ulandingiz! Endi hisobotlarni olib turasiz."
ONBOARD_START_BTN = "🚀 Sozlashni boshlash"
ONBOARD_DEFAULTS_BTN = "⚡ Standart bilan boshlash"

ASK_WORDS = "Kuniga (har seansda) nechta yangi so'z o'rganmoqchisiz?"
ASK_WEEKDAYS = "Qaysi kunlari o'rganasiz? Kunlarni belgilang, so'ng «Tayyor» bosing."
ASK_MORNING = "So'zlarni har kuni soat nechada yuboray? (yoki «Boshqa» bosib HH:MM yozing)"
ASK_EXAM = "Kechki imtihon vaqti nechada bo'lsin? (yoki «Boshqa» bosib HH:MM yozing)"
ASK_AUDIO = "So'zlar audio talaffuzi bilan yuborilsinmi?"
ASK_AUDIO_REPEAT = "Talaffuz necha marta takrorlansin?"
INVALID_TIME = "❌ Vaqt formati noto'g'ri. Iltimos HH:MM ko'rinishida yozing (masalan 07:30)."

WEEKDAY_NAMES = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
WEEKDAY_SHORT = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]

BTN_EVERYDAY = "Har kuni"
BTN_DONE = "✅ Tayyor"
BTN_OTHER = "Boshqa…"
BTN_AUDIO_ON = "🔊 Ha"
BTN_AUDIO_OFF = "🔇 Yo'q"
BTN_SAVE = "💾 Saqlash"
BTN_NUDGES_ON = "🔔 Yoqilgan"
BTN_NUDGES_OFF = "🔕 O'chirilgan"

ONBOARD_DONE = (
    "🎉 Ajoyib! Rejangiz saqlandi. Har kuni belgilangan vaqtda so'zlar yuboriladi.\n"
    "Sozlamalarni /settings orqali o'zgartirishingiz mumkin."
)

SETTINGS_TITLE = "⚙️ <b>Sizning sozlamalaringiz</b>"
SETTINGS_WORDS = "So'z / seans"
SETTINGS_DAYS = "O'quv kunlari"
SETTINGS_MORNING = "So'z vaqti"
SETTINGS_EXAM = "Imtihon vaqti"
SETTINGS_AUDIO = "Audio"
SETTINGS_NUDGES = "Eslatmalar"
SETTINGS_EDIT_HINT = "O'zgartirish uchun tegishli tugmani bosing."

PARENT_LINK = (
    "👨‍👩‍👧 Ota-ona rejimi.\nFarzandingizga shu havolani yuboring — u bosgach ulanadi va "
    "siz kunlik hisobot olib turasiz:\n\n{link}"
)
TEACHER_LINK = (
    "👨‍🏫 Ustoz rejimi.\nO'quvchingizga shu havolani yuboring — u bosgach ulanadi va "
    "siz kunlik hisobot olib turasiz:\n\n{link}"
)

HELP_TEXT = (
    "Buyruqlar:\n"
    "/start — boshlash / qayta ishga tushirish\n"
    "/menu — asosiy menyu (test, so'zlar, kitoblar, reyting)\n"
    "/settings — o'quv sozlamalarini ko'rish va o'zgartirish\n"
    "/cancel — joriy amalni bekor qilish\n"
    "/help — yordam"
)
CANCELLED = "Bekor qilindi."
NOTHING_TO_CANCEL = "Bekor qiladigan amal yo'q."
GENERIC_ERROR = "⚠️ Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring."

NO_WARDS = "Hali hech kim ulanmagan. /parent yoki /teacher bilan havola oling."
PICK_WARD = "Kimning hisobotini ko'rmoqchisiz?"

NUDGE_STUDY = "📚 So'zlarni takrorlayapsizmi? Kechqurun imtihon bor — tayyorlaning! 💪"
NUDGE_PRE_EXAM = "⏰ Imtihon vaqti yaqinlashdi! Tayyor bo'ling. 📝"
NUDGE_STREAK = "🔥 <b>{streak} kunlik streak!</b> Zo'r ketyapsiz, barakalla! 🎉"

TOP_TITLE = "🏆 <b>Oylik reyting</b>"
TOP_EMPTY = "Bu oyda hali natija yo'q. Imtihonlarni yakunlang! 💪"
TOP_YOUR_RANK = "Sizning o'rningiz: <b>{rank}</b> ({points} ball)"

PICK_BOOK_PDF = "📚 Qaysi kitobni PDF sifatida yuklab olasiz?"
NO_BOOKS = "Hozircha kitob mavjud emas."
PDF_SENDING = "⏳ Tayyorlanmoqda..."
PDF_ERROR = "Kechirasiz, PDF yuborishda xatolik yuz berdi."
PDF_NOT_AVAILABLE = "Bu kitob uchun PDF hozircha mavjud emas."

# Main menu (persistent reply keyboard)
MENU_TEST = "🧠 Test / Quiz"
MENU_WORDS = "📖 So'zlar ro'yxati"
MENU_BOOKS = "📚 Kitoblar"
MENU_GROUP_QUIZ = "👥 Guruh quizi"
MENU_TOP = "🏆 Reyting"
MENU_SETTINGS = "⚙️ Sozlamalar"
MENU_WEBAPP = "🌐 Mini App"
MENU_TODAY = "📅 Bugungi vazifa"
MENU_EXAM = "🎯 Imtihon"
TODAY_NONE = "📅 Bugungi vazifa hali yo'q — ertalab belgilangan vaqtda keladi 🌅"
TODAY_PREPARING = "⏳ Bugungi vazifa tayyorlanmoqda..."
MENU_OPENED = "🏠 <b>Asosiy menyu</b> 👇"

GROUP_QUIZ_INFO = (
    "👥 <b>Guruh quizi</b>\n\n"
    "Meni guruhingizga qo'shing 👇 so'ng admin <code>/quiz</code> yozib boshlasin — "
    "men ketma-ket quiz-savollar yuboraman va yakunda 🏆 reyting chiqaraman! 🔥"
)
GROUP_QUIZ_ADD_BTN = "➕ Guruhga qo'shish"

# Word list browser
WORDS_PICK_BOOK = "📖 Qaysi kitob so'zlarini ko'rasiz?"
WORDS_PICK_UNIT = "Qaysi bo'limdagi (unit) so'zlarni ko'rasiz?"
WORDS_EMPTY = "Bu bo'limda so'z topilmadi."
WORDS_HEADER = "📖 <b>{book} — Unit {unit}</b>\n"
BTN_BACK = "⬅️ Orqaga"
BTN_PREV = "⬅️"
BTN_NEXT = "➡️"
BTN_DETAIL = "📖 Batafsil"

# Personal practice quiz
QUIZ_PICK_BOOK = "🧠 Qaysi kitobdan mashq qilamiz?"
QUIZ_PICK_UNIT = "🎯 Bo'lim(lar)ni tanlang (bir nechta bo'lishi mumkin), so'ng «🚀 Boshlash»:"
QUIZ_PICK_UNIT_EMPTY = "Kamida bitta bo'lim tanlang 👆"
QUIZ_NO_WORDS = "Bu bo'lim(lar)da savol tuzishga so'z yetarli emas. 😔"
QUIZ_STARTING = "🧠 <b>{count} ta savol</b> — har biriga <b>30 soniya</b> ⏱ Tayyor bo'ling! 💪"
QUIZ_SKIPPED = "⏭ Javob berilmadi."
QUIZ_PAUSED = (
    "⏸ Ketma-ket 2 ta savolga javob bermadingiz — to'xtatildi. "
    "Davom etish: 🧠 Test / Quiz."
)
QUIZ_RESULT = "🏁 <b>Mashq tugadi!</b>\nNatija: <b>{correct}/{total}</b> to'g'ri 🎯"
QUIZ_LEARNED_MARKED = "📚 <b>{n}</b> so'z «o'rganilgan» deb belgilandi ✅"
BTN_ALL_UNITS = "🗂 Hammasi"
BTN_START = "🚀 Boshlash"
BTN_NEXT_STEP = "Keyingi ➡️"
BTN_DONE_TYPES = "✅ Tayyor"

QUIZ_PICK_COUNT = "🔢 Nechta savol bo'lsin?"
QUIZ_PICK_TIME = "⏱ Har savolga necha soniya?"
QUIZ_PICK_TYPES = "🎲 Savol turlarini tanlang, so'ng «✅ Tayyor»:"
QUIZ_TYPE_LABELS = {"en_uz": "🇬🇧→🇺🇿 EN→UZ", "uz_en": "🇺🇿→🇬🇧 UZ→EN", "def_word": "📖 Ta'rif→so'z"}

QUIZ_SUMMARY = (
    "🎯 <b>Test tayyor!</b>\n\n"
    "📚 <b>{book}</b>\n"
    "🗂 Bo'limlar: <b>{units}</b>\n"
    "✏️ <b>{count} ta savol</b>  ·  ⏱ <b>{time} soniya</b>\n"
    "🎲 Turlari: <b>{types}</b>"
)
BTN_START_HERE = "▶️ Bu testni boshlash"
BTN_START_GROUP = "👥 Guruhda testni boshlash"
BTN_SHARE = "🔗 Testni ulashish"
QUIZ_READY_PROMPT = "Tayyormisiz? 🎯"
SHARE_TEXT = "🧠 Men bu testni sizga ulashdim! «▶️ Testni boshlash» bosing 👇"
BTN_START_SHARED = "▶️ Testni boshlash"
SHARE_INLINE_HINT = (
    "💡 Istalgan chatda <code>@{username}</code> deb yozib, shu testni ulashishingiz mumkin."
)
SHARE_NO_USERNAME = "⚠️ Ulashish sozlanmagan (BOT_USERNAME yo'q). Admin bilan bog'laning."
BTN_PICK_GROUP = "👥 Guruhni tanlang"
GROUP_PICK_HINT = (
    "👥 Botni qo'shmoqchi bo'lgan guruhni tanlang — test o'sha guruhda "
    "shu sozlamalar bilan ochiladi 👇"
)
INLINE_NONE_TITLE = "Hali ulashilgan test yo'q"
INLINE_NONE_DESC = "Avval 🧠 Test/Quiz orqali test tuzing va «🔗 Testni ulashish» bosing."
INLINE_NONE_MSG = "Menda hali ulashish uchun test yo'q 🤷"

# Word-list audio (gTTS)
BTN_AUDIO = "🔊 Audio"
AUDIO_PREPARING = "🎧 Audio tayyorlanmoqda..."
AUDIO_FAILED = "😔 Audio hozircha tayyorlab bo'lmadi. Keyinroq urinib ko'ring."
