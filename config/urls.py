from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from apps.catalog import views as catalog_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Telegram Mini App (word browser) + its JSON data endpoints
    path("webapp/", catalog_views.webapp_index, name="webapp"),
    path("webapp/api/books/", catalog_views.api_books, name="webapp_books"),
    path("webapp/api/units/<int:book_id>/", catalog_views.api_units, name="webapp_units"),
    path("webapp/api/words/<int:unit_id>/", catalog_views.api_words, name="webapp_words"),
    path("webapp/api/search/", catalog_views.api_search, name="webapp_search"),
    path("webapp/api/profile/", catalog_views.api_profile, name="webapp_profile"),
    path("webapp/api/learned/", catalog_views.api_learned, name="webapp_learned"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
