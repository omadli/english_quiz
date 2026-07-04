import secrets

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


def _make_token() -> str:
    return secrets.token_urlsafe(16)


class ReferralToken(TimeStampedModel):
    class Role(models.TextChoices):
        PARENT = "parent", "Parent"
        TEACHER = "teacher", "Teacher"

    token = models.CharField(max_length=32, unique=True, db_index=True, default=_make_token)
    issuer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_tokens"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"ReferralToken({self.role}, active={self.is_active})"


class Guardianship(TimeStampedModel):
    class Role(models.TextChoices):
        PARENT = "parent", "Parent"
        TEACHER = "teacher", "Teacher"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    guardian = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wards_links"
    )
    learner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="guardian_links"
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["guardian", "learner"], name="uniq_guardian_learner")
        ]

    def __str__(self) -> str:
        return f"Guardianship({self.guardian_id}->{self.learner_id}, {self.role})"
