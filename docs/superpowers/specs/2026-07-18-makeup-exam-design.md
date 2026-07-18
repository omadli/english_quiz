# Missed-exam next-day makeup (C)

**Sana:** 2026-07-18 · **Holat:** shipped

## Muammo

Bugun imtihon vaqtida topshirilmagan `DailySession` abadiy `DELIVERED` bo'lib qoladi —
hech narsa uni yopmaydi, "missed" faqat dashboard'да o'qish vaqtida hisoblanadi. Foydalanuvchi
o'tkazib yuborilgan imtihonni ertasi kuni topshira olmaydi.

## Yechim (minimal — sana asosida, yangi status/task yo'q)

`api_exam` endi ikkita imtihon qaytaradi: **bugungi** + **kechagi** (`today-1`), ikkalasi
ham faqat tugallanmagan bo'lsa. Kechagisi — "qarzdorlik" (makeup). Topshirilsa `submit_exam`
o'sha sessiyani `COMPLETED` qiladi; `finalize_exam` `session.date` bo'yicha ishlaydi, ya'ni
kechagi kun yopiladi va **streak tabiiy tiklanadi** — alohida `completed_late` bayrog'i
kerak emas.

Retry oynasi = aynan bir kun: `today-1`. Ikki kun oldingi sessiya qaytarilmaydi (test bilan
qamralган). MISSED status, `retry_until` ustuni, yarim-tun Celery task — **hech biri kerak
emas**: sana filtri yetarli, va tugallanмаган kechagi sessiya sanaси o'zi retry oynasini
belgilaydi.

## O'zgarishlar

- `api_exam` → `{"exams": [{session_id, kind: "today"|"makeup", date, sections}]}` (avval
  `{"sections"}` edi — bitta imtihon).
- `api_submit_exam` → body'да `session_id`; server uni foydalanuvchiники VA `today`/`today-1`
  VA tugallanмаган ekanini tekshiradi (boshqaning yoki eski sessiyasini topshirib bo'lmaydi).
- Frontend `showToday`: makeup uchun amber "⏳ Kechagi imtihon — qarzdorlik" kartaси; `showExam(exam)`
  endi exam obyektini oladi; `submitExam(sessionId, answers)`.

## Ataylab qoldirilgan

- **"Kech" vizual belgisi yo'q**: makeup topshirilgach kechagi kun oddiy COMPLETED (yashil)
  bo'ladi. Streak tiklanishi muhimroq; kartа sarlavhasi "qarzdorlik" deb ogohlantiradi.
  Kerak bo'lsa `completed_late` bayrog'i keyin qo'shiladi.

## Tekshiruv

HTTP client testlari (8): today-only, +makeup, completed-yesterday omitted, submit by
session_id → COMPLETED, makeup heals yesterday, foreign session 400, two-day-old 400.
Brauzerда: makeup kartа render + o'ynab kechagi sessiya COMPLETED bo'lishi tasdiqlangan.
