from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import GroupQuizParticipant, GroupQuizQuestion, GroupQuizSession


@admin.register(GroupQuizSession)
class GroupQuizSessionAdmin(ModelAdmin):
    list_display = (
        "chat_id",
        "book",
        "status",
        "question_count",
        "interval_seconds",
        "started_at",
        "started_by_telegram_id",
    )
    list_filter = ("status",)
    raw_id_fields = ("book",)


@admin.register(GroupQuizQuestion)
class GroupQuizQuestionAdmin(ModelAdmin):
    list_display = ("session", "order", "word", "question_type", "poll_id")
    raw_id_fields = ("session", "word")


@admin.register(GroupQuizParticipant)
class GroupQuizParticipantAdmin(ModelAdmin):
    list_display = ("session", "telegram_id", "full_name", "correct_count", "total_time")
    raw_id_fields = ("session",)
