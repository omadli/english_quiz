from celery import shared_task


@shared_task
def ping() -> str:
    """Trivial task used to verify worker + broker wiring."""
    return "pong"
