from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from apps.accounts import views as accounts_views
from apps.catalog import views as catalog_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", accounts_views.landing, name="landing"),
    # Web app (Faza 5): passwordless login + dashboard
    path("login/", accounts_views.login_page, name="login"),
    path("logout/", accounts_views.logout_view, name="logout"),
    path("app/", accounts_views.dashboard, name="dashboard"),
    path("app/top/", accounts_views.leaderboard, name="leaderboard"),
    path("app/api/request-code/", accounts_views.api_request_code, name="request_code"),
    path("app/api/verify-code/", accounts_views.api_verify_code, name="verify_code"),
    path("app/api/session/", accounts_views.api_session_init, name="session_init"),
    # Telegram Mini App (word browser) + its JSON data endpoints
    path("webapp/", catalog_views.webapp_index, name="webapp"),
    path("webapp/api/books/", catalog_views.api_books, name="webapp_books"),
    path("webapp/api/units/<int:book_id>/", catalog_views.api_units, name="webapp_units"),
    path("webapp/api/words/<int:unit_id>/", catalog_views.api_words, name="webapp_words"),
    path("webapp/api/search/", catalog_views.api_search, name="webapp_search"),
    path("webapp/api/voice-sample/", catalog_views.api_voice_sample, name="webapp_voice_sample"),
    path("webapp/api/profile/", catalog_views.api_profile, name="webapp_profile"),
    path("webapp/api/learned/", catalog_views.api_learned, name="webapp_learned"),
    path("webapp/api/today/", catalog_views.api_today, name="webapp_today"),
    path("webapp/api/wards/", catalog_views.api_wards, name="webapp_wards"),
    path("webapp/api/ward/<int:learner_id>/settings/", catalog_views.api_ward_settings,
         name="webapp_ward_settings"),
    path("webapp/api/dashboard/", catalog_views.api_dashboard, name="webapp_dashboard"),
    path("webapp/api/ward/<int:learner_id>/dashboard/", catalog_views.api_ward_dashboard,
         name="webapp_ward_dashboard"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
