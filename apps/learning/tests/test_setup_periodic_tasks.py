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
