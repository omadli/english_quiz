import pytest

from apps.accounts.models import User
from apps.relations.models import ReferralToken
from apps.relations.services.referral import create_referral_token, redeem_token

pytestmark = pytest.mark.django_db


def test_create_token():
    issuer = User.objects.create(first_name="P")
    t = create_referral_token(issuer, ReferralToken.Role.PARENT)
    assert t.is_active is True
    assert t.issuer_id == issuer.id


def test_redeem_creates_guardianship_and_consumes_token():
    parent = User.objects.create(first_name="P")
    child = User.objects.create(first_name="C")
    t = create_referral_token(parent, ReferralToken.Role.PARENT)
    g = redeem_token(t.token, child)
    assert g is not None
    assert g.guardian_id == parent.id
    assert g.learner_id == child.id
    assert g.role == "parent"
    t.refresh_from_db()
    assert t.is_active is False
    assert t.used_by_id == child.id
    # cannot reuse
    assert redeem_token(t.token, child) is None


def test_redeem_unknown_token_returns_none():
    child = User.objects.create(first_name="C")
    assert redeem_token("nope", child) is None


def test_cannot_link_to_self():
    parent = User.objects.create(first_name="P")
    t = create_referral_token(parent, ReferralToken.Role.PARENT)
    assert redeem_token(t.token, parent) is None
