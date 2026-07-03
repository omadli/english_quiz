import datetime

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel


def default_weekdays() -> list[int]:
    """Mon..Sun as 0..6 — all days by default (fresh list each call)."""
    return [0, 1, 2, 3, 4, 5, 6]


class LearningProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learning_profile"
    )
    words_per_session = models.PositiveSmallIntegerField(default=10)
    study_weekdays = models.JSONField(default=default_weekdays)
    morning_time = models.TimeField(default=datetime.time(7, 0))
    exam_time = models.TimeField(default=datetime.time(20, 0))
    audio_enabled = models.BooleanField(default=True)
    audio_repeat = models.PositiveSmallIntegerField(default=2)
    timezone = models.CharField(max_length=40, default="Asia/Tashkent")
    language = models.CharField(max_length=8, default="uz")
    onboarded = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    current_book = models.ForeignKey(
        "catalog.Book", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    current_unit = models.ForeignKey(
        "catalog.Unit", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    current_word_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _("Learning profile")
        verbose_name_plural = _("Learning profiles")

    def studies_today(self, weekday: int) -> bool:
        return weekday in self.study_weekdays

    def __str__(self) -> str:
        return f"LearningProfile(user={self.user_id})"
