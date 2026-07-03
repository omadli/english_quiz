from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import TelegramAccount, User

admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    change_password_form = AdminPasswordChangeForm
    list_display = ("__str__", "first_name", "last_name", "phone_number", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active")
    search_fields = ("first_name", "last_name", "phone_number")
    ordering = ("id",)
    fieldsets = (
        (None, {"fields": ("first_name", "last_name", "phone_number", "password")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "is_active", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("first_name", "phone_number", "password1", "password2")}),
    )


@admin.register(TelegramAccount)
class TelegramAccountAdmin(ModelAdmin):
    list_display = ("telegram_id", "username", "user", "blocked_bot")
    search_fields = ("telegram_id", "username")
    raw_id_fields = ("user",)
