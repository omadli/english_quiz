from __future__ import annotations

import re

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import TimeStampedModel

_PRON_RE = re.compile(r"^\s*(\[[^\]]*\])?\s*(.*?)\s*$")


def parse_pronunciation(raw: str | None) -> tuple[str, str]:
    """Split e.g. '[əˈfreid] adj.' into ('[əˈfreid]', 'adj.')."""
    if not raw:
        return ("", "")
    match = _PRON_RE.match(raw)
    if not match:
        return ("", raw.strip())
    ipa = (match.group(1) or "").strip()
    pos = (match.group(2) or "").strip()
    return (ipa, pos)


class Book(TimeStampedModel):
    number = models.PositiveSmallIntegerField(unique=True, verbose_name=_("Number"))
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=8, blank=True)
    cover = models.ImageField(upload_to="images/books/covers/", blank=True, null=True)
    pdf = models.FileField(upload_to="books/pdf/", blank=True, null=True)
    word_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("number",)
        verbose_name = _("Book")
        verbose_name_plural = _("Books")

    def __str__(self) -> str:
        return self.title


class Unit(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="units")
    number = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=200, blank=True)
    word_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("book", "number")
        constraints = [models.UniqueConstraint(fields=["book", "number"], name="uniq_book_unit")]
        verbose_name = _("Unit")
        verbose_name_plural = _("Units")

    def __str__(self) -> str:
        return f"{self.book.title} — Unit {self.number}"


def word_image_upload_to(instance: "Word", filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1]
    return f"images/words/{instance.unit.book.number}/{instance.unit.number}/{instance.en}.{ext}"


def word_audio_upload_to(instance: "Word", filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1]
    return f"audio/words/{instance.unit.book.number}/{instance.unit.number}/{instance.en}.{ext}"


class Word(TimeStampedModel):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="words")
    order = models.PositiveSmallIntegerField(default=0)
    en = models.CharField(max_length=100, verbose_name=_("English"))
    uz = models.CharField(max_length=255, verbose_name=_("Uzbek"))
    part_of_speech = models.CharField(max_length=20, blank=True)
    pronunciation = models.CharField(max_length=100, blank=True)
    definition = models.TextField(blank=True)
    example = models.TextField(blank=True)
    image = models.ImageField(upload_to=word_image_upload_to, blank=True, null=True)
    audio_en = models.FileField(upload_to=word_audio_upload_to, blank=True, null=True)
    audio_uz = models.FileField(upload_to=word_audio_upload_to, blank=True, null=True)

    class Meta:
        ordering = ("unit", "order")
        constraints = [models.UniqueConstraint(fields=["unit", "en"], name="uniq_unit_word")]
        indexes = [models.Index(fields=["en"])]
        verbose_name = _("Word")
        verbose_name_plural = _("Words")

    @property
    def book(self) -> Book:
        return self.unit.book

    def __str__(self) -> str:
        return f"{self.en} — {self.uz}"
