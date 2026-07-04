from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


def _empty_list() -> list:
    return []


class GroupQuizSession(TimeStampedModel):
    class Status(models.TextChoices):
        CONFIGURING = "configuring", "Configuring"
        RUNNING = "running", "Running"
        FINISHED = "finished", "Finished"
        ABORTED = "aborted", "Aborted"

    chat_id = models.BigIntegerField(db_index=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    book = models.ForeignKey(
        "catalog.Book", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    unit_ids = models.JSONField(default=_empty_list)
    question_types = models.JSONField(default=_empty_list)
    question_count = models.PositiveSmallIntegerField(default=10)
    interval_seconds = models.PositiveSmallIntegerField(default=20)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIGURING)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"GroupQuizSession(chat={self.chat_id}, {self.status})"


class GroupQuizQuestion(TimeStampedModel):
    session = models.ForeignKey(
        GroupQuizSession, on_delete=models.CASCADE, related_name="questions"
    )
    word = models.ForeignKey("catalog.Word", on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=0)
    question_type = models.CharField(max_length=10)
    poll_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)  # noqa: DJ001
    sent_at = models.DateTimeField(null=True, blank=True)
    options = models.JSONField(default=_empty_list)
    correct_option = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ("order",)

    def __str__(self) -> str:
        return f"GroupQuizQuestion(session={self.session_id}, order={self.order})"


class GroupQuizParticipant(TimeStampedModel):
    session = models.ForeignKey(
        GroupQuizSession, on_delete=models.CASCADE, related_name="participants"
    )
    telegram_id = models.BigIntegerField()
    username = models.CharField(max_length=64, blank=True, default="")
    full_name = models.CharField(max_length=128, blank=True, default="")
    correct_count = models.PositiveSmallIntegerField(default=0)
    total_time = models.FloatField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "telegram_id"], name="uniq_session_participant"
            )
        ]

    def __str__(self) -> str:
        return f"GroupQuizParticipant(session={self.session_id}, tg={self.telegram_id})"
