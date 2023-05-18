from django.contrib.auth.base_user import BaseUserManager, AbstractBaseUser
from django.utils.translation import gettext_lazy as _
from typing import Union


class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """
    def create_user(self, first_name, phone_number, password, **extra_fields):
        """
        Create and save a User with the given phone_number and password.
        """
        if not phone_number:
            raise ValueError(_('Telefon raqam kiritish majburiy!'))
        if not first_name:
            raise ValueError(_('Ism kiritish majburiy!'))
        phone_number = self.normalize_phone(phone_number)
        user: AbstractBaseUser = self.model(first_name=first_name, phone_number=phone_number, **extra_fields)  # noqa: E501
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, phone_number, password, first_name, **extra_fields):
        """
        Create and save a SuperUser with the given phone_number and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(first_name, phone_number, password, **extra_fields)

    def normalize_phone(self, phone_number: Union[str, int]):
        if isinstance(phone_number, int):
            phone_number = str(phone_number)
        
        phone_number = phone_number.replace(" ", "")
        phone_number = phone_number.replace("-", "")
        if phone_number.startswith("+"):
            phone_number = phone_number[1:]
        if not phone_number.startswith("998"):
            if len(phone_number) == 9:
                phone_number = "998"+phone_number
            else:
                raise ValueError(_("Faqat O'zbekiston raqamlari mumkin!"))
        if phone_number.isnumeric():
            phone_number = int(phone_number)
        else:
            raise ValueError(_("998911234567 formatda kiriting"))
        return phone_number
            
