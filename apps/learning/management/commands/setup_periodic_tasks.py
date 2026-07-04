from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Register the recurring Celery Beat tasks (idempotent)."

    def handle(self, *args, **options):
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=60, period=IntervalSchedule.SECONDS
        )
        PeriodicTask.objects.update_or_create(
            name="dispatch_morning_deliveries",
            defaults={
                "interval": schedule,
                "task": "apps.learning.tasks.dispatch_morning_deliveries",
            },
        )
        self.stdout.write(self.style.SUCCESS("periodic tasks registered"))
