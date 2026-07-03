from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .models import Book, Unit, Word


class UnitInline(TabularInline):
    model = Unit
    extra = 0
    fields = ("number", "title", "word_count")
    readonly_fields = ("word_count",)


class WordInline(TabularInline):
    model = Word
    extra = 0
    fields = ("order", "en", "uz", "part_of_speech")


@admin.register(Book)
class BookAdmin(ModelAdmin):
    list_display = ("number", "title", "level", "word_count", "is_active")
    search_fields = ("title",)
    inlines = (UnitInline,)


@admin.register(Unit)
class UnitAdmin(ModelAdmin):
    list_display = ("__str__", "book", "number", "word_count")
    list_filter = ("book",)
    inlines = (WordInline,)


@admin.register(Word)
class WordAdmin(ModelAdmin):
    list_display = ("en", "uz", "part_of_speech", "unit", "thumb")
    list_display_links = ("en",)
    list_filter = ("unit__book", "part_of_speech")
    search_fields = ("en", "uz")
    list_select_related = ("unit", "unit__book")

    @admin.display(description="image")
    def thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:36px;border-radius:4px" />', obj.image.url
            )
        return "—"
