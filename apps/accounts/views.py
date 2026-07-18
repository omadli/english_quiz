import json

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST

from apps.accounts.models import TelegramAccount
from apps.accounts.services.login import create_login_request, verify_login_request
from apps.common.webapp_auth import parse_init_data

_BACKEND = "django.contrib.auth.backends.ModelBackend"  # required: we bypass authenticate()


def landing(request):
    """Public marketing homepage."""
    return render(request, "web/landing.html", {"bot_username": settings.BOT_USERNAME})


@ensure_csrf_cookie  # guarantee the csrftoken cookie is set for the JS fetch POSTs
def login_page(request):
    if request.user.is_authenticated:
        return redirect("/app/")
    return render(request, "web/login.html")


def _json_body(request) -> dict:
    try:
        data = json.loads(request.body or b"{}")
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


@require_POST
def api_login_link(request):
    """Start a login: mint a nonce and return the bot deep link to open."""
    if not settings.BOT_USERNAME:
        return JsonResponse({"ok": False, "error": "no_bot"}, status=503)
    nonce = create_login_request()
    url = f"https://t.me/{settings.BOT_USERNAME}?start=login_{nonce}"
    return JsonResponse({"ok": True, "nonce": nonce, "url": url})


@require_POST
def api_verify_code(request):
    body = _json_body(request)
    user = verify_login_request(body.get("nonce", ""), body.get("code", ""))
    if user is None:
        return JsonResponse({"ok": False, "error": "invalid"}, status=400)
    login(request, user, backend=_BACKEND)  # rotates the session key (anti-fixation)
    return JsonResponse({"ok": True, "redirect": "/app/"})


@csrf_exempt  # auth is the initData HMAC, not a session cookie
def api_session_init(request):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    init_data = _json_body(request).get("init_data") or request.headers.get(
        "X-Telegram-Init-Data", ""
    )
    data = parse_init_data(init_data)
    if data is None:
        return JsonResponse({"ok": False}, status=401)
    account = (
        TelegramAccount.objects.select_related("user").filter(telegram_id=data.user.id).first()
    )
    if account is None or not account.user.is_active:
        return JsonResponse({"ok": False}, status=401)
    login(request, account.user, backend=_BACKEND)
    return JsonResponse({"ok": True, "redirect": "/app/"})


@login_required
def dashboard(request):
    from apps.learning.services.dashboard import build_dashboard

    return render(
        request,
        "web/dashboard.html",
        {"d": build_dashboard(request.user), "bot_username": settings.BOT_USERNAME},
    )


@login_required
def leaderboard(request):
    from django.utils import timezone

    from apps.learning.services.ranking import build_monthly_leaderboard, user_month_rank

    today = timezone.localdate()
    rows = build_monthly_leaderboard(today.year, today.month, limit=20)
    mine = user_month_rank(request.user, today.year, today.month)
    return render(
        request,
        "web/leaderboard.html",
        {
            "rows": rows,
            "mine": mine,
            "month": today,
            "in_top": any(r["user_id"] == request.user.id for r in rows),
        },
    )


@require_POST  # a GET <img src="/logout/"> must not be able to log the user out
def logout_view(request):
    logout(request)
    return redirect("/login/")
