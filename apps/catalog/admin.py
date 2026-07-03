from django.contrib import admin

from .models import Book, Unit, Word


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "level", "word_count", "is_active")
    list_filter = ("is_active", "level")
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("book", "number", "title", "word_count")
    list_filter = ("book",)
    search_fields = ("title", "slug")


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ("id", "en", "uz", "unit", "part_of_speech")
    list_display_links = ("id", "en")
    list_filter = ("unit__book", "unit")
    list_editable = ("uz",)
    search_fields = ("en", "uz")
