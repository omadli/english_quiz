from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import DailySession, ExamQuestion, LearningProfile, WordProgress


@admin.register(LearningProfile)
class LearningProfileAdmin(ModelAdmin):
    list_display = ("user", "words_per_session", "onboarded", "is_active", "current_book")
    list_filter = ("onboarded", "is_active", "audio_enabled")
    raw_id_fields = ("user", "current_book", "current_unit")
    search_fields = ("user__first_name", "user__last_name")


@admin.register(DailySession)
class DailySessionAdmin(ModelAdmin):
    list_display = ("user", "date", "status", "score", "total", "delivered_at")
    list_filter = ("status", "date")
    raw_id_fields = ("user", "book", "unit")
    date_hierarchy = "date"


@admin.register(WordProgress)
class WordProgressAdmin(ModelAdmin):
    list_display = ("user", "word", "status", "repetitions", "ease_factor", "next_review")
    list_filter = ("status",)
    raw_id_fields = ("user", "word")
    search_fields = ("word__en",)


@admin.register(ExamQuestion)
class ExamQuestionAdmin(ModelAdmin):
    list_display = ("daily_session", "word", "question_type", "is_correct", "answered_at")
    list_filter = ("question_type", "is_correct")
    raw_id_fields = ("daily_session", "word")
    search_fields = ("poll_id", "word__en")
