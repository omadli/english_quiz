from apps.learning.models import LearningProfile
from apps.relations.models import Guardianship


def active_guardianship(guardian, learner_id) -> Guardianship | None:
    return Guardianship.objects.filter(
        guardian=guardian, learner_id=learner_id, status=Guardianship.Status.ACTIVE
    ).first()


def ward_profile(guardian, learner_id) -> LearningProfile | None:
    """The ward's LearningProfile — only if the caller is an active guardian."""
    if active_guardianship(guardian, learner_id) is None:
        return None
    profile, _ = LearningProfile.objects.get_or_create(user_id=learner_id)
    return profile


def revoke(guardian, learner_id) -> bool:
    link = active_guardianship(guardian, learner_id)
    if link is None:
        return False
    link.status = Guardianship.Status.REVOKED
    link.save(update_fields=["status", "updated_at"])
    return True
