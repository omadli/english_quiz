from django.utils import timezone

from apps.relations.models import Guardianship, ReferralToken


def create_referral_token(issuer, role: str) -> ReferralToken:
    return ReferralToken.objects.create(issuer=issuer, role=role)


def redeem_token(token_str: str, learner) -> Guardianship | None:
    token = (
        ReferralToken.objects.select_related("issuer")
        .filter(token=token_str, is_active=True)
        .first()
    )
    if token is None or token.issuer_id == learner.id:
        return None
    guardianship, _ = Guardianship.objects.get_or_create(
        guardian=token.issuer, learner=learner, defaults={"role": token.role}
    )
    token.is_active = False
    token.used_by = learner
    token.used_at = timezone.now()
    token.save(update_fields=["is_active", "used_by", "used_at", "updated_at"])
    return guardianship
