"""Outcome progress from compatible observations only. Pure functions over (date, value) points.

Status vocabulary:
  needs_source  no connected source can measure this metric
  not_started   window has not begun
  unknown       no compatible data (or no baseline) to evaluate
  partial       some data, but gaps or data-through short of what is needed
  in_progress   window open, coverage complete so far
  met / not_met window ended (or flow already past target) with complete coverage
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

RULE_VERSION = "outcome-progress-v1"


@dataclass
class Progress:
    status: str
    value: int | None = None
    target: int | None = None
    baseline: int | None = None
    baseline_date: date | None = None
    current_date: date | None = None
    data_through: date | None = None
    required_days: int = 0
    observed_days: int = 0
    missing_days: list = field(default_factory=list)
    pace_guide: float | None = None
    notes: list = field(default_factory=list)
    version_ids: list = field(default_factory=list)
    rule_version: str = RULE_VERSION

    @property
    def coverage(self):
        if not self.required_days:
            return None
        return self.observed_days / self.required_days

    @property
    def fraction(self):
        if self.value is None or not self.target:
            return None
        return max(0.0, min(1.0, self.value / self.target))


STATUS_LABEL = {
    "needs_source": "Needs source",
    "not_started": "Not started",
    "unknown": "Unknown",
    "partial": "Partial data",
    "in_progress": "In progress",
    "met": "Met",
    "not_met": "Not met",
}
STATUS_TONE = {"met": "good", "not_met": "bad", "partial": "warn", "unknown": "warn", "needs_source": "warn", "in_progress": "neutral", "not_started": "neutral"}


def _days(start, end):
    d = start
    while d < end:
        yield d
        d += timedelta(days=1)


def compute(kind, mode, target, period_start, period_end, today, points, has_source=True, baseline_max_gap_days=7):
    """points: list of (date, value, version_id), each a daily observation/snapshot. period_end is exclusive.

    today: the current day on the outcome's date basis (UTC for Spotify days).
    """
    p = Progress(status="unknown", target=target)
    if not has_source:
        p.status = "needs_source"
        p.notes.append("No connected source measures this yet. Progress stays unknown, not zero.")
        return p
    by_day = {d: (v, vid) for d, v, vid in points}
    p.data_through = max(by_day) if by_day else None
    if today < period_start:
        p.status = "not_started"
        return p
    window_ended = today >= period_end
    if kind == "flow":
        return _flow_total(p, by_day, period_start, period_end, today, window_ended)
    if kind in ("stock", "rolling_stock", "nested_stock", "cumulative"):
        if mode == "gain":
            return _stock_gain(p, by_day, period_start, period_end, today, window_ended, baseline_max_gap_days)
        return _level(p, by_day, period_start, period_end, today, window_ended)
    p.status = "unknown"
    p.notes.append("This metric cannot be an outcome (a sum of daily unique counts is not a count of people).")
    return p


def _pace(p, period_start, period_end, today):
    elapsed = (min(today, period_end) - period_start).days
    total = (period_end - period_start).days
    if total > 0 and p.target is not None:
        p.pace_guide = p.target * elapsed / total


def _flow_total(p, by_day, start, end, today, ended):
    # Spotify publishes a day after it closes; the evaluable range ends at data-through, never past the window.
    horizon = min(end, today)
    required = list(_days(start, horizon))
    observed = [d for d in required if d in by_day]
    p.required_days = len(required)
    p.observed_days = len(observed)
    p.missing_days = [d for d in required if d not in by_day]
    if not observed:
        p.status = "unknown"
        p.notes.append("No observations in this window yet.")
        return p
    p.value = sum(by_day[d][0] for d in observed)
    p.version_ids = [by_day[d][1] for d in observed]
    _pace(p, start, end, today)
    complete_window = all(d in by_day for d in _days(start, end))
    if p.value >= p.target:
        p.status = "met"
        if not complete_window:
            p.notes.append("Target already reached from the observed days.")
    elif ended and complete_window:
        p.status = "not_met"
    elif ended:
        p.status = "partial"
        p.notes.append(f"Window ended but data covers only {p.observed_days} of {(end - start).days} days; not evaluated.")
    elif p.missing_days:
        trailing = p.data_through is not None and all(d > p.data_through for d in p.missing_days)
        p.status = "in_progress" if trailing and len(p.missing_days) <= 2 else "partial"
        if p.status == "partial":
            p.notes.append(f"{len(p.missing_days)} days missing inside the window.")
        else:
            p.notes.append(f"Data through {p.data_through.isoformat()}.")
    else:
        p.status = "in_progress"
    return p


def _latest_at_or_before(by_day, limit_exclusive):
    days = [d for d in by_day if d < limit_exclusive]
    return max(days) if days else None


def _stock_gain(p, by_day, start, end, today, ended, max_gap):
    # Baseline: latest snapshot closing at or before the window start (day < start), within the allowed gap.
    base_day = _latest_at_or_before(by_day, start)
    if base_day is None or (start - base_day).days > max_gap + 1:
        p.status = "unknown"
        p.notes.append(f"No compatible starting snapshot within {max_gap} days before {start.isoformat()}. Gain is unknown, not zero.")
        return p
    p.baseline, p.baseline_date = by_day[base_day][0], base_day
    current_day = _latest_at_or_before(by_day, min(end, today + timedelta(days=1)))
    if current_day is None or current_day < start:
        p.status = "unknown"
        p.notes.append("No snapshot inside the window yet.")
        return p
    p.current_date = current_day
    p.value = by_day[current_day][0] - p.baseline
    p.version_ids = [by_day[base_day][1], by_day[current_day][1]]
    p.required_days = 1
    p.observed_days = 1
    _pace(p, start, end, today)
    last_needed = end - timedelta(days=1)
    if ended and (last_needed - current_day).days <= max_gap:
        p.status = "met" if p.value >= p.target else "not_met"
    elif ended:
        p.status = "partial"
        p.notes.append(f"Latest snapshot is {current_day.isoformat()}, too early to evaluate the window end.")
    else:
        p.status = "in_progress"
    return p


def _level(p, by_day, start, end, today, ended):
    current_day = _latest_at_or_before(by_day, min(end, today + timedelta(days=1)))
    if current_day is None:
        p.status = "unknown"
        p.notes.append("No snapshot yet.")
        return p
    p.current_date = current_day
    p.value = by_day[current_day][0]
    p.version_ids = [by_day[current_day][1]]
    p.required_days = 1
    p.observed_days = 1
    if p.value >= p.target:
        p.status = "met" if ended or current_day >= start else "in_progress"
    elif ended:
        p.status = "not_met" if (end - timedelta(days=1) - current_day).days <= 7 else "partial"
    else:
        p.status = "in_progress"
    return p


# Descriptive aggregation helpers (metric algebra) used by Today and Evidence.


def aggregate(kind, points):
    """points: list of (date, value). Returns (value, method) using only the valid aggregation for the kind."""
    if not points:
        return None, "none"
    if kind == "flow":
        return sum(v for _, v in points), "sum"
    if kind in ("stock", "rolling_stock", "nested_stock", "cumulative"):
        d, v = max(points)
        return v, f"latest ({d.isoformat()})"
    if kind == "daily_unique":
        d, v = max(points)
        return v, f"single day ({d.isoformat()}); days are not summed"
    raise ValueError(kind)


def ratio(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def net_tickets(snapshots):
    """Latest cumulative net snapshot. Successive totals replace each other; they are never summed."""
    if not snapshots:
        return None
    latest = max(snapshots, key=lambda s: s["at"])
    return latest["paid"] + latest.get("issued", 0) - latest.get("refunded", 0) - latest.get("cancelled", 0)
