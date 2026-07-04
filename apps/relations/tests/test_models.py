import pytest
from django.db import IntegrityError

from apps.accounts.models import User
from apps.relations.models import Guardianship, ReferralToken

pytestmark = pytest.mark.django_db


def test_referral_token_auto_token_and_defaults():
    issuer = User.objects.create(first_name="P")
    t = ReferralToken.objects.create(issuer=issuer, role=ReferralToken.Role.PARENT)
    assert t.token  # auto-generated, non-empty
    assert t.is_active is True
    assert t.used_by is None
    # two tokens differ
    t2 = ReferralToken.objects.create(issuer=issuer, role=ReferralToken.Role.PARENT)
    assert t.token != t2.token


def test_guardianship_unique_per_pair():
    g = User.objects.create(first_name="G")
    learner = User.objects.create(first_name="L")
    Guardianship.objects.create(guardian=g, learner=learner, role=Guardianship.Role.PARENT)
    assert g.wards_links.count() == 1
    assert learner.guardian_links.count() == 1
    with pytest.raises(IntegrityError):
        Guardianship.objects.create(guardian=g, learner=learner, role=Guardianship.Role.TEACHER)


def test_settings_present(settings):
    assert isinstance(settings.GUARDIAN_REPORT_HOUR, int)
    assert isinstance(settings.BOT_USERNAME, str)
