from apps.accounts.models import TelegramAccount, User
from apps.catalog.models import Book
from apps.learning.models import LearningProfile


def get_or_create_user(
    telegram_id: int,
    username: str,
    first_name: str,
    last_name: str,
    language_code: str,
) -> tuple[User, LearningProfile, bool]:
    """Find or create the User + TelegramAccount + LearningProfile for a Telegram user."""
    try:
        account = TelegramAccount.objects.select_related("user").get(telegram_id=telegram_id)
        account.username = username
        account.first_name = first_name
        account.last_name = last_name
        account.language_code = language_code
        account.save(
            update_fields=["username", "first_name", "last_name", "language_code", "updated_at"]
        )
        user = account.user
        profile, _ = LearningProfile.objects.get_or_create(user=user)
        return user, profile, False
    except TelegramAccount.DoesNotExist:
        user = User.objects.create(
            first_name=first_name or "Foydalanuvchi", last_name=last_name or ""
        )
        TelegramAccount.objects.create(
            user=user,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )
        profile = LearningProfile.objects.create(user=user)
        return user, profile, True


def update_profile(profile: LearningProfile, **fields) -> LearningProfile:
    for key, value in fields.items():
        setattr(profile, key, value)
    profile.save(update_fields=[*fields.keys(), "updated_at"])
    return profile


def set_starting_position(profile: LearningProfile) -> LearningProfile:
    book = Book.objects.filter(is_active=True).order_by("number").first()
    if book is None:
        return profile
    unit = book.units.order_by("number").first()
    profile.current_book = book
    profile.current_unit = unit
    profile.current_word_order = 0
    profile.save(update_fields=["current_book", "current_unit", "current_word_order", "updated_at"])
    return profile


def apply_wizard_data(profile: LearningProfile, data: dict) -> LearningProfile:
    """Persist collected wizard settings, mark onboarded, and set the starting position."""
    for key in (
        "words_per_session",
        "study_weekdays",
        "morning_time",
        "exam_time",
        "audio_enabled",
        "audio_repeat",
    ):
        if key in data:
            setattr(profile, key, data[key])
    profile.onboarded = True
    profile.save()
    set_starting_position(profile)
    return profile
