from __future__ import annotations
from django.db import models
from django.utils.translation import gettext as _
from django.core.validators import MinValueValidator, MaxValueValidator

from .utils import speach


def upload_word_image(instance: Word, filename):
    ext = filename.split('.')[-1]
    
    # file will be uploaded to MEDIA_ROOT / images / words / <book_number> / <unit_number> / <word_number>  # noqa: E501
    return 'images/words/{0}/{1}/{2}.{3}'.format(instance.book, instance.unit, instance.en, ext)  # noqa: E501

class Word(models.Model):
    id = models.AutoField(null=False, primary_key=True)
    book = models.PositiveSmallIntegerField(
        null=False, blank=False, help_text=_("Kitob raqami"),
        validators=[
            MinValueValidator(1),
            MaxValueValidator(6)
        ]
    )
    
    unit = models.PositiveSmallIntegerField(
        null=False, blank=False, help_text=_("Unit raqami"),
        validators=[
            MinValueValidator(1),
            MaxValueValidator(30)
        ]
    )
    
    en = models.CharField(
        max_length=100, null=False,
        verbose_name="english",
        db_column='en',
        help_text="Inglizchasi",
    )
    uz = models.CharField(
        max_length=100, null=False, db_column='uz',
        verbose_name="uzbek",
        help_text=_("O'zbekcha tarjimasi"),
    )
    definition = models.TextField(
        null=True, blank=True,
        help_text=_("Ta'rifi"),
    )
    example = models.TextField(
        null=True, blank=True,
        help_text=_("Namuna"),
    )
    pronunciation = models.CharField(
        null=True, blank=True, max_length=100,
        help_text=_("Talaffuzi")
    )
    
    image = models.ImageField(
        null=True, blank=True,
        upload_to=upload_word_image
    )

    def voice(self, slow: bool = False):
        return speach(self.en, slow)
    
    
    def __str__(self) -> str:
        return self.en + " - " + self.uz
    
    class Meta:
        ordering = ("id", )
        # unique_together = ('book', 'unit', 'en')
        constraints = [
            models.UniqueConstraint(fields=["book", "en"], name='book and word'),   # noqa: E501
        ]
