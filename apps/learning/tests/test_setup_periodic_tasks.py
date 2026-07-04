import pytest
from django.core.management import call_command
from django_celery_beat.models import PeriodicTask

pytestmark = pytest.mark.django_db


def test_setup_registers_dispatch_task():
    call_command("setup_periodic_tasks")
    task = PeriodicTask.objects.get(name="dispatch_morning_deliveries")
    assert task.task == "apps.learning.tasks.dispatch_morning_deliveries"
    assert task.interval.every == 60
    # idempotent
    call_command("setup_periodic_tasks")
    assert PeriodicTask.objects.filter(name="dispatch_morning_deliveries").count() == 1


def test_setup_registers_exam_tasks():
    from django_celery_beat.models import PeriodicTask

    call_command("setup_periodic_tasks")
    assert PeriodicTask.objects.get(name="dispatch_evening_exams").task == (
        "apps.learning.tasks.dispatch_evening_exams"
    )
    assert PeriodicTask.objects.get(name="finalize_due_exams").task == (
        "apps.learning.tasks.finalize_due_exams"
    )
    # idempotent
    call_command("setup_periodic_tasks")
    assert PeriodicTask.objects.filter(name="dispatch_evening_exams").count() == 1


def test_setup_registers_guardian_report_crontab():
    from django_celery_beat.models import PeriodicTask

    call_command("setup_periodic_tasks")
    task = PeriodicTask.objects.get(name="dispatch_guardian_reports")
    assert task.task == "apps.relations.tasks.dispatch_guardian_reports"
    assert task.crontab is not None
    # idempotent
    call_command("setup_periodic_tasks")
    assert PeriodicTask.objects.filter(name="dispatch_guardian_reports").count() == 1


def test_setup_registers_nudge_tasks():
    from django_celery_beat.models import PeriodicTask

    call_command("setup_periodic_tasks")
    for name in ("dispatch_study_nudges", "dispatch_pre_exam_nudges", "dispatch_practice_polls"):
        assert PeriodicTask.objects.filter(name=name).count() == 1
    # existing tasks intact
    assert PeriodicTask.objects.filter(name="dispatch_morning_deliveries").exists()
    assert PeriodicTask.objects.filter(name="dispatch_guardian_reports").exists()
    # idempotent
    call_command("setup_periodic_tasks")
    assert PeriodicTask.objects.filter(name="dispatch_study_nudges").count() == 1
