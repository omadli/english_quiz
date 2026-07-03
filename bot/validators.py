import datetime


def parse_time(text: str) -> datetime.time | None:
    """Parse 'HH:MM' (24h). Return None if malformed or out of range."""
    parts = text.strip().split(":")
    if len(parts) != 2:
        return None
    hh, mm = parts
    if not (hh.isdecimal() and mm.isdecimal()):
        return None
    hour, minute = int(hh), int(mm)
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return datetime.time(hour, minute)
    return None


def toggle_weekday(days: list[int], day: int) -> list[int]:
    """Add day if absent, remove if present. Returns a new sorted list."""
    result = set(days)
    if day in result:
        result.discard(day)
    else:
        result.add(day)
    return sorted(result)
