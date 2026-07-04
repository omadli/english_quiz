from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Register the recurring Celery Beat tasks (idempotent)."

    def handle(self, *args, **options):
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=60, period=IntervalSchedule.SECONDS
        )
        tasks = {
            "dispatch_morning_deliveries": "apps.learning.tasks.dispatch_morning_deliveries",
            "dispatch_evening_exams": "apps.learning.tasks.dispatch_evening_exams",
            "finalize_due_exams": "apps.learning.tasks.finalize_due_exams",
        }
        for name, task in tasks.items():
            PeriodicTask.objects.update_or_create(
                name=name, defaults={"interval": schedule, "task": task}
            )
        self.stdout.write(self.style.SUCCESS("periodic tasks registered"))
