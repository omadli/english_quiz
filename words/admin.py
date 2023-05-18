from django.contrib import admin

from .models import Word

@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ("id", "book", "unit", "en", "uz")
    model = Word
    list_filter = ("book", "unit")
    