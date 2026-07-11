import html

from django.core.management.base import BaseCommand

from apps.catalog.models import Word


class Command(BaseCommand):
    help = (
        "Decode HTML entities (&ldquo; &rsquo; &nbsp; …) left in word example/definition/uz "
        "text so they render as real characters everywhere. Idempotent."
    )

    def handle(self, *args, **opts) -> None:
        fixed = 0
        for w in Word.objects.iterator():
            ex, de, uz = html.unescape(w.example), html.unescape(w.definition), html.unescape(w.uz)
            if (ex, de, uz) != (w.example, w.definition, w.uz):
                w.example, w.definition, w.uz = ex, de, uz
                w.save(update_fields=["example", "definition", "uz", "updated_at"])
                fixed += 1
        self.stdout.write(self.style.SUCCESS(f"decoded HTML entities in {fixed} words"))
