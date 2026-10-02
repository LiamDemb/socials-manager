"""Pure scheduling and execution-state rules. No database access."""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from core.errors import DomainError

TERMINAL = {"completed": "Completed", "skipped": "Skipped", "cancelled": "Cancelled"}


def local_to_utc(day: date, at: time, tz_name: str) -> datetime:
    """Convert a wall-clock time, rejecting nonexistent and ambiguous local times instead of guessing."""
    tz = ZoneInfo(tz_name)
    naive = datetime.combine(day, at)
    first = naive.replace(tzinfo=tz, fold=0)
    second = naive.replace(tzinfo=tz, fold=1)
    roundtrip = first.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)
    if roundtrip != naive:
        raise DomainError(
            "nonexistent_local_time",
            f"{at.strftime('%H:%M')} on {day.isoformat()} does not exist in {tz_name} (clocks move forward). Choose another time.",
            fields={"time": "Does not exist on this date"},
        )
    if first.utcoffset() != second.utcoffset():
        raise DomainError(
            "ambiguous_local_time",
            f"{at.strftime('%H:%M')} on {day.isoformat()} happens twice in {tz_name} (clocks move back). Choose another time.",
            fields={"time": "Ambiguous on this date"},
        )
    return first.astimezone(timezone.utc)


def local_today(now_utc: datetime, tz_name: str) -> date:
    return now_utc.astimezone(ZoneInfo(tz_name)).date()


def derived_state(status, planned_at_utc, all_day_date, now_utc, tz_name):
    """Display state. Persisted terminal states override clock-derived labels."""
    if status in TERMINAL:
        return TERMINAL[status]
    if planned_at_utc is None and all_day_date is None:
        return "Unscheduled"
    today = local_today(now_utc, tz_name)
    if planned_at_utc is not None:
        if planned_at_utc <= now_utc:
            return "Overdue"
        if planned_at_utc.astimezone(ZoneInfo(tz_name)).date() == today:
            return "Due today"
        return "Upcoming"
    if all_day_date < today:
        return "Overdue"
    if all_day_date == today:
        return "Due today"
    return "Upcoming"


STATE_TONE = {
    "Completed": "good",
    "Due today": "warn",
    "Overdue": "bad",
    "Upcoming": "neutral",
    "Unscheduled": "neutral",
    "Skipped": "muted",
    "Cancelled": "muted",
}


def planned_local_date(planned_at_utc, all_day_date, tz_name):
    if all_day_date:
        return all_day_date
    if planned_at_utc:
        return planned_at_utc.astimezone(ZoneInfo(tz_name)).date()
    return None
