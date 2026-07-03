from apps.common.tasks import ping


def test_ping_runs_eagerly(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    assert ping.apply().get() == "pong"


def test_ping_is_registered():
    from config.celery import app

    assert "apps.common.tasks.ping" in app.tasks
