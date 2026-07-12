import datetime
import json
import time

from aiogram.utils.web_app import safe_parse_webapp_init_data
from django.conf import settings
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import TelegramAccount
from apps.catalog.models import Book, Unit, Word
from apps.common.tts import EN_VOICES, UZ_VOICES
from apps.learning.models import DailySession, LearnedWord, LearningProfile
from apps.relations.services.guardian import ward_profile
from apps.relations.services.reports import guardian_wards


def _word_payload(w: Word, with_context: bool = False) -> dict:
    data = {
        "id": w.id,
        "en": w.en,
        "uz": w.uz,
        "part_of_speech": w.part_of_speech,
        "pronunciation": w.pronunciation,
        "definition": w.definition,
        "example": w.example,
        "image": w.image.url if w.image else None,
    }
    if with_context:
        data["book"] = w.unit.book.number
        data["unit"] = w.unit.number
    return data


def webapp_index(request):
    """The Telegram Mini App page (word browser). Data loads from the JSON
    endpoints below; the page itself is a self-contained template."""
    return render(request, "webapp/index.html")


def api_books(request):
    books = [
        {
            "id": b.id,
            "number": b.number,
            "title": b.title,
            "word_count": b.word_count,
            "pdf": b.pdf.url if b.pdf else None,
            "cover": b.cover.url if b.cover else None,
        }
        for b in Book.objects.filter(is_active=True).order_by("number")
    ]
    return JsonResponse({"books": books})


def api_units(request, book_id: int):
    units = list(
        Unit.objects.filter(book_id=book_id)
        .order_by("number")
        .values("id", "number", "title", "word_count")
    )
    # When the caller is authenticated (Telegram initData), attach per-unit
    # learned counts so the Mini App can draw the progress path.
    profile = _profile_from_request(request)
    if profile is not None:
        counts = dict(
            LearnedWord.objects.filter(user=profile.user, word__unit__book_id=book_id)
            .values("word__unit_id")
            .annotate(c=Count("id"))
            .values_list("word__unit_id", "c")
        )
        for u in units:
            u["learned"] = counts.get(u["id"], 0)
    return JsonResponse({"units": units})


def api_words(request, unit_id: int):
    words = Word.objects.filter(unit_id=unit_id).select_related("unit").order_by("order")
    return JsonResponse({"words": [_word_payload(w) for w in words]})


def api_search(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"words": []})
    words = (
        Word.objects.filter(Q(en__icontains=query) | Q(uz__icontains=query))
        .select_related("unit", "unit__book")
        .order_by("en")[:50]
    )
    return JsonResponse({"words": [_word_payload(w, with_context=True) for w in words]})


# ---- Mini App settings (Telegram initData-authenticated) --------------------
_INIT_DATA_MAX_AGE = 86400  # seconds; reject stale/replayed initData


def _profile_from_request(request) -> LearningProfile | None:
    """Resolve the caller's LearningProfile from a validated Telegram initData header."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data or not settings.BOT_TOKEN:
        return None
    try:
        data = safe_parse_webapp_init_data(token=settings.BOT_TOKEN, init_data=init_data)
    except ValueError:
        return None  # bad/forged signature
    if data.user is None or time.time() - data.auth_date.timestamp() > _INIT_DATA_MAX_AGE:
        return None
    account = (
        TelegramAccount.objects.select_related("user").filter(telegram_id=data.user.id).first()
    )
    if account is None:
        return None
    profile, _ = LearningProfile.objects.get_or_create(user=account.user)
    return profile


def _profile_payload(profile: LearningProfile) -> dict:
    return {
        "words_per_session": profile.words_per_session,
        "study_weekdays": profile.study_weekdays,
        "morning_time": profile.morning_time.strftime("%H:%M"),
        "exam_time": profile.exam_time.strftime("%H:%M"),
        "audio_enabled": profile.audio_enabled,
        "audio_repeat": profile.audio_repeat,
        "nudges_enabled": profile.nudges_enabled,
        "en_voice": profile.en_voice,
        "uz_voice": profile.uz_voice,
        "en_voices": EN_VOICES,
        "uz_voices": UZ_VOICES,
        "learned_words": LearnedWord.objects.filter(user=profile.user).count(),
    }


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_hhmm(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError:
        return None


def _clean_settings(payload: dict) -> dict:
    """Validate/coerce incoming settings at the trust boundary — drop anything invalid."""
    updates = {}
    wps = _as_int(payload.get("words_per_session")) if "words_per_session" in payload else None
    if wps is not None and 1 <= wps <= 50:
        updates["words_per_session"] = wps
    rep = _as_int(payload.get("audio_repeat")) if "audio_repeat" in payload else None
    if rep is not None and 1 <= rep <= 5:
        updates["audio_repeat"] = rep
    if isinstance(payload.get("study_weekdays"), list):
        updates["study_weekdays"] = sorted(
            {d for d in payload["study_weekdays"] if isinstance(d, int) and 0 <= d <= 6}
        )
    for key in ("morning_time", "exam_time"):
        if key in payload:
            parsed = _parse_hhmm(payload[key])
            if parsed is not None:
                updates[key] = parsed
    for key in ("audio_enabled", "nudges_enabled"):
        if key in payload:
            updates[key] = bool(payload[key])
    if payload.get("en_voice") in {v[0] for v in EN_VOICES}:
        updates["en_voice"] = payload["en_voice"]
    if payload.get("uz_voice") in {v[0] for v in UZ_VOICES}:
        updates["uz_voice"] = payload["uz_voice"]
    return updates


@csrf_exempt  # auth is the initData HMAC, not a session cookie
def api_profile(request):
    profile = _profile_from_request(request)
    if profile is None:
        return JsonResponse({"error": "unauthorized"}, status=401)
    if request.method == "POST":
        try:
            payload = json.loads(request.body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "bad json"}, status=400)
        updates = _clean_settings(payload if isinstance(payload, dict) else {})
        if updates:
            for key, value in updates.items():
                setattr(profile, key, value)
            profile.save(update_fields=[*updates.keys(), "updated_at"])
    return JsonResponse(_profile_payload(profile))


@csrf_exempt  # auth is the initData HMAC, not a session cookie
def api_today(request):
    """Today's daily-session words for the caller (the morning task), replayable in-app."""
    profile = _profile_from_request(request)
    if profile is None:
        return JsonResponse({"error": "unauthorized"}, status=401)
    from zoneinfo import ZoneInfo

    today = timezone.now().astimezone(ZoneInfo(profile.timezone)).date()
    session = DailySession.objects.filter(user=profile.user, date=today).first()
    if session is None:
        return JsonResponse({"words": [], "status": "none"})
    words = [
        sw.word
        for sw in session.session_words.select_related("word__unit__book").order_by("order")
    ]
    return JsonResponse({
        "status": session.status,
        "date": today.isoformat(),
        "words": [_word_payload(w, with_context=True) for w in words],
    })


@csrf_exempt  # auth is the initData HMAC, not a session cookie
def api_wards(request):
    """The caller's active wards (guardian view)."""
    profile = _profile_from_request(request)
    if profile is None:
        return JsonResponse({"error": "unauthorized"}, status=401)
    wards = guardian_wards(profile.user)
    return JsonResponse(
        {"wards": [{"id": w.id, "name": w.full_name or str(w.pk)} for w in wards]}
    )


@csrf_exempt  # auth is the initData HMAC, not a session cookie
def api_ward_settings(request, learner_id: int):
    """GET/POST one ward's settings — only for the ward's active guardian."""
    caller = _profile_from_request(request)
    if caller is None:
        return JsonResponse({"error": "unauthorized"}, status=401)
    profile = ward_profile(caller.user, learner_id)
    if profile is None:
        return JsonResponse({"error": "forbidden"}, status=403)
    if request.method == "POST":
        try:
            payload = json.loads(request.body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "bad json"}, status=400)
        updates = _clean_settings(payload if isinstance(payload, dict) else {})
        if updates:
            for key, value in updates.items():
                setattr(profile, key, value)
            profile.save(update_fields=[*updates.keys(), "updated_at"])
    return JsonResponse(_profile_payload(profile))


@csrf_exempt  # auth is the initData HMAC, not a session cookie
def api_learned(request):
    """GET → the user's learned word ids (read-only). Learned state is earned by
    completing tests (marked bot-side), not toggled manually — there is no POST."""
    profile = _profile_from_request(request)
    if profile is None:
        return JsonResponse({"error": "unauthorized"}, status=401)
    ids = list(LearnedWord.objects.filter(user=profile.user).values_list("word_id", flat=True))
    return JsonResponse({"ids": ids})
