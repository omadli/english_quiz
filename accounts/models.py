from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _
from django.core.validators import RegexValidator
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin

from .managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(
        null=False, blank=False, max_length=100,
        verbose_name=_("Ism"),
        help_text=_("Foydalanuvchi ismi"),
    )
    last_name = models.CharField(
        null=True, blank=True, default=None, max_length=100,
        verbose_name=_("Familiya"),
        help_text=_("Foydalanuvchi familiyasi"),
    )
    phone_number = models.BigIntegerField(
        null=False, blank=False, unique=True,
        verbose_name=_('Telefon raqam'),
        help_text=_("998911234567 formatda kiriting."),
        validators=[
            RegexValidator(
                regex=r"^(\+?)998(90|91|93|94|95|97|98|99|33|88|77)[0-9]{7}$",
            ),
        ]
    )
    password = models.CharField(
        null=False, blank=False,
        verbose_name=_("Parol"), max_length=128,
    )
    
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now,)
    
    @property
    def full_name(self):
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        else:
            return self.first_name
    
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name',]

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.full_name} +{self.phone_number}"

    class Meta:
        db_table = 'users'
        verbose_name = _("User")
        verbose_name_plural = _("Users")
