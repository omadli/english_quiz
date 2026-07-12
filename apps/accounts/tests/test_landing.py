import pytest


@pytest.mark.django_db
def test_landing_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Essential Words" in r.content
    assert b"Telegram" in r.content


@pytest.mark.django_db
def test_landing_shows_login_when_anonymous(client):
    assert b"/login/" in client.get("/").content


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    assert client.get("/app/").status_code == 302  # -> /login/


@pytest.mark.django_db
def test_dashboard_renders_for_user(client):
    from apps.accounts.models import User
    from apps.learning.models import LearningProfile

    u = User.objects.create(first_name="Ali")
    LearningProfile.objects.create(user=u)
    client.force_login(u)
    r = client.get("/app/")
    assert r.status_code == 200
    assert b"seriya" in r.content
    assert b"Aniqlik trendi" in r.content


@pytest.mark.django_db
def test_leaderboard_requires_login(client):
    assert client.get("/app/top/").status_code == 302


@pytest.mark.django_db
def test_leaderboard_renders_for_user(client):
    from apps.accounts.models import User

    u = User.objects.create(first_name="Ali")
    client.force_login(u)
    r = client.get("/app/top/")
    assert r.status_code == 200
    assert b"reyting" in r.content.lower()
