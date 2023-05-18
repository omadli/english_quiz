from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import User


# admin.site.unregister(User)
admin.site.unregister(Group)

# @admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    list_display = ('first_name', 'last_name', 'phone_number', 'is_superuser', 'is_staff', 'is_active', 'date_joined')  # noqa: E501
    list_filter = ('is_staff', 'is_active', 'date_joined')
    fieldsets = (
        (None, {'fields': ('first_name', 'last_name', 'phone_number', 'password')}),
        ('Permissions', {'fields': ('is_staff', 'is_active')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'phone_number', 'password1', 'password2', 'is_staff', 'is_superuser')}  # noqa: E501
        ),
    )
    search_fields = ('phone_number__contains', 'first_name__icontains', 'last_name__icontains')  # noqa: E501
    ordering = ('id',)


admin.site.register(User, CustomUserAdmin)
