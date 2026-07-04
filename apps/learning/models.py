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


class DailySession(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERED = "delivered", "Delivered"
        EXAM_SENT = "exam_sent", "Exam sent"
        COMPLETED = "completed", "Completed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_sessions"
    )
    date = models.DateField()
    book = models.ForeignKey(
        "catalog.Book", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    unit = models.ForeignKey(
        "catalog.Unit", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    words = models.ManyToManyField(
        "catalog.Word", through="SessionWord", related_name="daily_sessions"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    delivered_at = models.DateTimeField(null=True, blank=True)
    exam_sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    total = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("-date",)
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="uniq_user_daily_session")
        ]

    def __str__(self) -> str:
        return f"DailySession(user={self.user_id}, {self.date})"


class SessionWord(models.Model):
    daily_session = models.ForeignKey(
        DailySession, on_delete=models.CASCADE, related_name="session_words"
    )
    word = models.ForeignKey("catalog.Word", on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("order",)

    def __str__(self) -> str:
        return f"SessionWord(session={self.daily_session_id}, word={self.word_id})"


class WordProgress(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        LEARNING = "learning", "Learning"
        KNOWN = "known", "Known"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="word_progress"
    )
    word = models.ForeignKey("catalog.Word", on_delete=models.CASCADE, related_name="progress")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    repetitions = models.PositiveSmallIntegerField(default=0)
    ease_factor = models.FloatField(default=2.5)
    interval_days = models.PositiveSmallIntegerField(default=0)
    next_review = models.DateField(null=True, blank=True)
    correct_count = models.PositiveSmallIntegerField(default=0)
    wrong_count = models.PositiveSmallIntegerField(default=0)
    last_reviewed = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "word"], name="uniq_user_word_progress")
        ]

    def __str__(self) -> str:
        return f"WordProgress(user={self.user_id}, word={self.word_id})"


class ExamQuestion(TimeStampedModel):
    class QType(models.TextChoices):
        EN_UZ = "en_uz", "EN→UZ"
        UZ_EN = "uz_en", "UZ→EN"
        DEF_WORD = "def_word", "Definition"

    daily_session = models.ForeignKey(
        DailySession, on_delete=models.CASCADE, related_name="questions"
    )
    word = models.ForeignKey("catalog.Word", on_delete=models.CASCADE)
    question_type = models.CharField(max_length=10, choices=QType.choices)
    poll_id = models.CharField(max_length=64, unique=True, db_index=True)
    options = models.JSONField(default=list)
    correct_option = models.PositiveSmallIntegerField()
    chosen_option = models.PositiveSmallIntegerField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return f"ExamQuestion(session={self.daily_session_id}, word={self.word_id})"
