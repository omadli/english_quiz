from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import LearningProfile


@admin.register(LearningProfile)
class LearningProfileAdmin(ModelAdmin):
    list_display = ("user", "words_per_session", "onboarded", "is_active", "current_book")
    list_filter = ("onboarded", "is_active", "audio_enabled")
    raw_id_fields = ("user", "current_book", "current_unit")
    search_fields = ("user__first_name", "user__last_name")
