from __future__ import annotations

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.catalog.models import Word
from apps.common.tts import get_tts_provider

REMOTE_MP3 = (
    "https://www.essentialenglish.review/apps-data/"
    "4000-essential-english-words-{book}/data/mp3/{name}.mp3"
)


class Command(BaseCommand):
    help = "Populate Word.audio_en from the source site's mp3 or via gTTS."

    def add_arguments(self, parser):
        parser.add_argument("--book", type=int, default=None)
        parser.add_argument("--source", choices=["remote", "gtts"], default="remote")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **opts):
        provider = get_tts_provider()
        qs = Word.objects.select_related("unit__book")
        if opts["book"]:
            qs = qs.filter(unit__book__number=opts["book"])
        if not opts["overwrite"]:
            qs = qs.filter(audio_en="")
        done = 0
        for word in qs.iterator():
            data = None
            if opts["source"] == "remote":
                data = self._fetch_remote(word)
            if data is None:
                data = provider.synthesize(word.en, lang="en")
            word.audio_en.save(f"{word.en}.mp3", ContentFile(data), save=True)
            done += 1
        self.stdout.write(self.style.SUCCESS(f"audio synced: {done} words"))

    def _fetch_remote(self, word: Word) -> bytes | None:
        url = REMOTE_MP3.format(book=word.unit.book.number, name=word.en)
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200 and resp.content:
                return resp.content
        except requests.RequestException as exc:
            self.stderr.write(self.style.WARNING(f"remote miss {word.en}: {exc}"))
        return None
