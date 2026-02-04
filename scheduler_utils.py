from datetime import datetime, timedelta


DAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


def parse_time(time_str: str | None) -> tuple[int, int]:
    if not time_str:
        return 9, 0
    try:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return hour, minute
    except Exception:
        return 9, 0


def parse_days(days_str: str | None) -> list[int]:
    if not days_str:
        return []
    days = []
    for part in days_str.split(","):
        key = part.strip().lower()
        if key in DAY_MAP:
            days.append(DAY_MAP[key])
    return sorted(set(days))


def compute_next_run(
    frequency: str,
    scheduled_time: str | None,
    scheduled_days: str | None,
    from_time: datetime | None = None,
) -> datetime | None:
    if frequency == "once":
        return None

    from_time = from_time or datetime.utcnow()
    hour, minute = parse_time(scheduled_time)
    base = from_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if frequency == "daily":
        if base <= from_time:
            base += timedelta(days=1)
        return base

    if frequency in ["weekly", "custom"]:
        valid_days = parse_days(scheduled_days)
        if not valid_days:
            valid_days = [from_time.weekday()]
        for offset in range(0, 8):
            candidate = base + timedelta(days=offset)
            if candidate.weekday() in valid_days and candidate > from_time:
                return candidate
        return base + timedelta(days=7)

    return None
