import pytest

from apps.accounts.models import User
from apps.learning.models import LearningProfile
from apps.relations.models import Guardianship
from apps.relations.services import guardian as g

pytestmark = pytest.mark.django_db


def _pair():
    guardian = User.objects.create(first_name="Mom")
    learner = User.objects.create(first_name="Kid")
    return guardian, learner


def test_active_guardianship_only_when_active():
    guardian, learner = _pair()
    link = Guardianship.objects.create(guardian=guardian, learner=learner, role="parent")
    assert g.active_guardianship(guardian, learner.id) == link
    link.status = Guardianship.Status.REVOKED
    link.save()
    assert g.active_guardianship(guardian, learner.id) is None


def test_ward_profile_guarded():
    guardian, learner = _pair()
    assert g.ward_profile(guardian, learner.id) is None  # not linked
    Guardianship.objects.create(guardian=guardian, learner=learner, role="parent")
    prof = g.ward_profile(guardian, learner.id)
    assert isinstance(prof, LearningProfile)
    assert prof.user_id == learner.id


def test_revoke():
    guardian, learner = _pair()
    Guardianship.objects.create(guardian=guardian, learner=learner, role="teacher")
    assert g.revoke(guardian, learner.id) is True
    assert g.active_guardianship(guardian, learner.id) is None
    assert g.revoke(guardian, learner.id) is False  # already revoked
