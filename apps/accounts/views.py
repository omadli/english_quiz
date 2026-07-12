import json
import time

from aiogram.utils.web_app import safe_parse_webapp_init_data
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST

from apps.accounts.models import TelegramAccount
from apps.accounts.services.login import request_login_code, verify_login_code

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


def api_request_code(request):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    identifier = _json_body(request).get("identifier", "")
    return JsonResponse(request_login_code(identifier))


def api_verify_code(request):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    body = _json_body(request)
    user = verify_login_code(body.get("identifier", ""), body.get("code", ""))
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
    if not init_data or not settings.BOT_TOKEN:
        return JsonResponse({"ok": False}, status=401)
    try:
        data = safe_parse_webapp_init_data(token=settings.BOT_TOKEN, init_data=init_data)
    except ValueError:
        return JsonResponse({"ok": False}, status=401)
    if data.user is None or time.time() - data.auth_date.timestamp() > 86400:
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


@require_POST  # a GET <img src="/logout/"> must not be able to log the user out
def logout_view(request):
    logout(request)
    return redirect("/login/")
