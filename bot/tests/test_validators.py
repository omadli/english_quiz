import datetime

import pytest

from bot.validators import parse_time, toggle_weekday


@pytest.mark.parametrize(
    "text,expected",
    [
        ("07:30", datetime.time(7, 30)),
        ("7:5", datetime.time(7, 5)),
        ("23:59", datetime.time(23, 59)),
        ("00:00", datetime.time(0, 0)),
        ("24:00", None),
        ("07:60", None),
        ("abc", None),
        ("", None),
        ("7", None),
        ("0²:00", None),
        ("²:²", None),
    ],
)
def test_parse_time(text, expected):
    assert parse_time(text) == expected


def test_toggle_weekday_adds_and_removes():
    assert toggle_weekday([0, 2], 1) == [0, 1, 2]
    assert toggle_weekday([0, 1, 2], 1) == [0, 2]
    assert toggle_weekday([], 5) == [5]
