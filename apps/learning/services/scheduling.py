from datetime import datetime
from zoneinfo import ZoneInfo

from apps.learning.models import LearningProfile


def is_due_for_delivery(profile: LearningProfile, now_utc: datetime) -> bool:
    """True if this profile should receive its morning delivery at `now_utc`."""
    if not profile.is_active or not profile.onboarded:
        return False
    local = now_utc.astimezone(ZoneInfo(profile.timezone))
    if local.weekday() not in profile.study_weekdays:
        return False
    return local.hour == profile.morning_time.hour and local.minute == profile.morning_time.minute


def is_due_for_exam(profile: LearningProfile, now_utc: datetime) -> bool:
    """True if this profile should receive its evening exam at `now_utc`."""
    if not profile.is_active or not profile.onboarded:
        return False
    local = now_utc.astimezone(ZoneInfo(profile.timezone))
    if local.weekday() not in profile.study_weekdays:
        return False
    return local.hour == profile.exam_time.hour and local.minute == profile.exam_time.minute
