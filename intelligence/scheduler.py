"""Deterministic scheduling with disclosed fallbacks."""
from datetime import date, time, timedelta

from core import instance
from core.errors import DomainError

RULE_VERSION = "scheduler-v1"
DEFAULT_EVENING = time(18, 0)


def campaign_phase(campaign_type, key_date: date | None, day: date, start: date, end: date) -> str:
    from .contracts import campaign_phase_type

    phase_type = campaign_phase_type(campaign_type)
    if phase_type == "growth":
        return "sustain"
    if not key_date:
        return "sustain"
    if day < key_date:
        return "pre_release"
    if day == key_date:
        return "launch"
    if (day - key_date).days <= 7:
        return "sustain"
    return "show_week" if phase_type == "show" else "sustain"


def feasible_days(start: date, end: date, assets_ready: date | None, blackouts: list[date]) -> list[date]:
    black = set(blackouts or [])
    first = start
    if assets_ready and assets_ready > first:
        first = assets_ready
    days = []
    d = first
    while d <= end:
        if d not in black:
            days.append(d)
        d += timedelta(days=1)
    return days


def pick_time_slot(day: date, campaign_type, timing_evidence: dict | None, tz_name: str) -> dict:
    """Return SchedulingDecision fields. Uses synthetic evening window when no timing evidence."""
    basis = "Campaign constraint"
    fallback = True
    chosen_local = f"{day.isoformat()}T{DEFAULT_EVENING.strftime('%H:%M')}"
    feasible = [{"local": chosen_local, "score": 0}]
    if timing_evidence and timing_evidence.get("preferred_hour") is not None and timing_evidence.get("refs"):
        hour = int(timing_evidence["preferred_hour"])
        chosen_local = f"{day.isoformat()}T{hour:02d}:00"
        n = timing_evidence.get("sample_n") or (timing_evidence.get("refs") or [{}])[0].get("n")
        lim = timing_evidence.get("limitation") or ""
        basis = f"Timing evidence (n={n})" if n else "Timing evidence"
        if lim:
            basis = f"{basis}; {lim[:80]}"
        fallback = False
        feasible = [{"local": chosen_local, "window": timing_evidence.get("window", "18:00-20:00"), "score": 1}]
    cfg = instance.load()
    if cfg.get("default_post_time"):
        try:
            t = time.fromisoformat(cfg["default_post_time"])
            chosen_local = f"{day.isoformat()}T{t.strftime('%H:%M')}"
            if fallback:
                basis = "Your default post time"
        except ValueError:
            pass
    return {
        "chosen_local": chosen_local,
        "timezone": tz_name,
        "basis": basis,
        "fallback": fallback,
        "feasible_candidates": feasible,
        "requested_window": {"day": day.isoformat()},
        "rule_version": RULE_VERSION,
        "evidence_refs": timing_evidence.get("refs", []) if timing_evidence else [],
    }


def attach_schedule(activity_fields: dict, schedule: dict) -> dict:
    from campaigns import services as campaign_services
    from catalogue.services import parse_date

    day = parse_date(schedule["chosen_local"][:10], "date")
    time_text = schedule["chosen_local"][11:16] if "T" in schedule["chosen_local"] else None
    tz = schedule["timezone"]
    merged = {**activity_fields, **campaign_services._activity_time_fields(day, time_text, tz)}
    merged["origin_detail"] = {
        **(activity_fields.get("origin_detail") or {}),
        "scheduling_basis": schedule["basis"],
        "scheduling_fallback": schedule["fallback"],
        "rule_version": schedule["rule_version"],
    }
    return merged
