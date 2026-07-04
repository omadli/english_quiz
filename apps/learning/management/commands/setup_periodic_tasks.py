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
            "dispatch_pre_exam_nudges": "apps.learning.tasks.dispatch_pre_exam_nudges",
        }
        for name, task in tasks.items():
            PeriodicTask.objects.update_or_create(
                name=name, defaults={"interval": schedule, "task": task}
            )

        from django.conf import settings
        from django_celery_beat.models import CrontabSchedule

        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour=str(settings.GUARDIAN_REPORT_HOUR),
            day_of_week="*", day_of_month="*", month_of_year="*",
        )
        PeriodicTask.objects.update_or_create(
            name="dispatch_guardian_reports",
            defaults={"crontab": crontab, "interval": None,
                      "task": "apps.relations.tasks.dispatch_guardian_reports"},
        )

        study_cron, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour=str(settings.STUDY_NUDGE_HOUR),
            day_of_week="*", day_of_month="*", month_of_year="*",
        )
        PeriodicTask.objects.update_or_create(
            name="dispatch_study_nudges",
            defaults={"crontab": study_cron, "interval": None,
                      "task": "apps.learning.tasks.dispatch_study_nudges"},
        )
        practice_cron, _ = CrontabSchedule.objects.get_or_create(
            minute="0", hour=str(settings.PRACTICE_POLL_HOUR),
            day_of_week="*", day_of_month="*", month_of_year="*",
        )
        PeriodicTask.objects.update_or_create(
            name="dispatch_practice_polls",
            defaults={"crontab": practice_cron, "interval": None,
                      "task": "apps.learning.tasks.dispatch_practice_polls"},
        )
        self.stdout.write(self.style.SUCCESS("periodic tasks registered"))
