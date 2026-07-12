import datetime

import pytest

from apps.accounts.models import User
from apps.learning.models import LearningProfile, default_weekdays

pytestmark = pytest.mark.django_db


def _user():
    return User.objects.create(first_name="Test")


def test_profile_defaults():
    p = LearningProfile.objects.create(user=_user())
    assert p.words_per_session == 10
    assert p.study_weekdays == [0, 1, 2, 3, 4, 5, 6]
    assert p.morning_time == datetime.time(7, 0)
    assert p.exam_time == datetime.time(20, 0)
    assert p.audio_enabled is True
    assert p.audio_repeat == 2
    assert p.timezone == "Asia/Tashkent"
    assert p.onboarded is False
    assert p.is_active is True
    assert p.current_word_order == 0
    assert p.en_voice == "en-US-AriaNeural"
    assert p.uz_voice == "uz-UZ-MadinaNeural"


def test_studies_today():
    p = LearningProfile.objects.create(user=_user(), study_weekdays=[0, 2, 4])
    assert p.studies_today(0) is True
    assert p.studies_today(1) is False


def test_default_weekdays_is_a_fresh_list():
    first = default_weekdays()
    first.append(99)
    assert default_weekdays() == [0, 1, 2, 3, 4, 5, 6]
