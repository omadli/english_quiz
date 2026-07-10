from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel

from .managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length=100, verbose_name=_("Name"))
    last_name = models.CharField(max_length=100, blank=True, default="", verbose_name=_("Surname"))
    phone_number = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        verbose_name=_("Phone number"),
        validators=[
            RegexValidator(regex=r"^998(90|91|93|94|95|97|98|99|33|88|77|20)[0-9]{7}$"),
        ],
    )
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["first_name"]

    objects = CustomUserManager()

    class Meta:
        db_table = "users"
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.first_name

    def get_username(self) -> str:
        # USERNAME_FIELD is phone_number (BigIntegerField). AbstractBaseUser's
        # default get_username() returns that raw int, which breaks any code
        # (e.g. django-unfold's avatar template) that expects a string it can
        # slice/index. Stringify it here; auth itself queries USERNAME_FIELD
        # directly and doesn't go through this method.
        value = getattr(self, self.USERNAME_FIELD)
        return str(value) if value is not None else ""

    def __str__(self) -> str:
        if self.phone_number:
            return f"{self.full_name} +{self.phone_number}"
        return self.full_name or str(self.pk)


class LoginCode(TimeStampedModel):
    """A short-lived one-time code DM'd to the user's Telegram for web login."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_codes")
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["user", "used"])]

    def __str__(self) -> str:
        return f"LoginCode(user={self.user_id}, used={self.used})"


class TelegramAccount(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="telegram")
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=64, blank=True, default="")
    first_name = models.CharField(max_length=128, blank=True, default="")
    last_name = models.CharField(max_length=128, blank=True, default="")
    language_code = models.CharField(max_length=8, blank=True, default="")
    is_premium = models.BooleanField(default=False)
    blocked_bot = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Telegram account")
        verbose_name_plural = _("Telegram accounts")

    def __str__(self) -> str:
        return f"@{self.username}" if self.username else str(self.telegram_id)
