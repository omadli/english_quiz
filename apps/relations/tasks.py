from celery import shared_task
from django.utils import timezone

from apps.relations.models import Guardianship
from apps.relations.services.reports import build_learner_report
from bot.sender import send_text


@shared_task
def dispatch_guardian_reports() -> None:
    date = timezone.localdate()
    links = Guardianship.objects.filter(status=Guardianship.Status.ACTIVE).select_related(
        "guardian__telegram", "learner"
    )
    for link in links.iterator():
        account = getattr(link.guardian, "telegram", None)
        if account is None or account.blocked_bot:
            continue
        text = build_learner_report(link.learner, date)
        send_text(account.telegram_id, text)
