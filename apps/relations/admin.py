from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Guardianship, ReferralToken


@admin.register(ReferralToken)
class ReferralTokenAdmin(ModelAdmin):
    list_display = ("token", "issuer", "role", "is_active", "used_by", "used_at")
    list_filter = ("role", "is_active")
    raw_id_fields = ("issuer", "used_by")


@admin.register(Guardianship)
class GuardianshipAdmin(ModelAdmin):
    list_display = ("guardian", "learner", "role", "status")
    list_filter = ("role", "status")
    raw_id_fields = ("guardian", "learner")
