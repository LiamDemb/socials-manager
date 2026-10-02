"""Read-only view models. Every figure comes from stored observations; nothing here invents values."""
import calendar as pycal
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from campaigns import measurement, rules
from campaigns.models import Activity, Campaign
from campaigns.services import deduplicated_outcomes, describe_outcome, display_state, has_source, outcome_progress
from catalogue.services import own_artist
from core import clock, instance
from sources.models import ImportBatch, MetricDefinition, Observation
from sources.services import committed_entities, series

TONE = {"Completed": "good", "Due today": "warn", "Overdue": "bad", "Upcoming": "neutral", "Skipped": "muted",
        "Cancelled": "muted", "Unscheduled": "muted"}

TREND_METRICS = [
    ("spotify.artist.streams.v1", "sum"),
    ("spotify.artist.followers.v1", "stock"),
    ("spotify.artist.monthly_listeners.v1", "stock"),
    ("spotify.artist.saves.v1", "sum"),
]


def config():
    return instance.load()


def local_now():
    return clock.now().astimezone(ZoneInfo(config()["timezone"]))


def freshness(through):
    """Spotify days are UTC; a file exported today normally runs to yesterday or the day before."""
    if through is None:
        return {"state": "none", "label": "No data", "days_old": None}
    days_old = (clock.now().date() - through).days
    stale = days_old > config()["stale_after_days"]
    return {"state": "stale" if stale else "fresh", "days_old": days_old,
            "label": f"Data through {through.strftime('%-d %b %Y')} (UTC)" + (f", {days_old} days old" if stale else "")}


def trend_cards():
    artist = own_artist()
    if artist is None:
        return []
    cards = []
    for metric_id, how in TREND_METRICS:
        metric = MetricDefinition.objects.get(pk=metric_id)
        points = series(artist.entity, metric_id, purpose="descriptive_derive")
        if not points:
            cards.append({"metric": metric, "value": None, "fresh": freshness(None)})
            continue
        through = points[-1][0]
        by_day = {d: v for d, v, _ in points}
        current_window = [through - timedelta(days=i) for i in range(7)]
        previous_window = [through - timedelta(days=i) for i in range(7, 14)]
        complete = all(d in by_day for d in current_window)
        prev_complete = all(d in by_day for d in previous_window)
        if how == "sum":
            value = sum(by_day[d] for d in current_window if d in by_day) if complete else None
            previous = sum(by_day[d] for d in previous_window) if prev_complete else None
            window = f"{current_window[-1].strftime('%-d %b')} to {through.strftime('%-d %b')}"
            comparison = "previous 7 days"
        else:
            value = by_day[through]
            earlier = through - timedelta(days=7)
            previous = by_day.get(earlier)
            window = f"as of {through.strftime('%-d %b')}"
            comparison = f"{earlier.strftime('%-d %b')}"
        change = None if value is None or previous is None else value - previous
        cards.append({"metric": metric, "value": value, "previous": previous, "change": change, "window": window,
                      "comparison": comparison, "fresh": freshness(through), "incomplete": how == "sum" and not complete})
    return cards


def coverage_rows():
    rows = []
    for entity in committed_entities():
        metric_ids = Observation.objects.filter(entity=entity, active_version__isnull=False).values_list("metric_id", flat=True).distinct()
        for metric in MetricDefinition.objects.filter(pk__in=list(metric_ids)).order_by("label"):
            days = sorted(d for d, _, _ in series(entity, metric.pk))
            if not days:
                continue
            span = (days[-1] - days[0]).days + 1
            rows.append({"entity": entity, "metric": metric, "first": days[0], "through": days[-1], "days": len(days),
                         "missing": span - len(days), "fresh": freshness(days[-1])})
    return rows


def outcome_rows(campaigns_qs=None):
    rows = []
    for entry in deduplicated_outcomes(campaigns_qs):
        ov = entry["ov"]
        progress = outcome_progress(ov)
        rows.append({
            "ov": ov, "title": describe_outcome(ov), "progress": progress, "campaigns": entry["campaigns"],
            "status_label": measurement.STATUS_LABEL[progress.status], "tone": measurement.STATUS_TONE[progress.status],
            "percent": round(progress.fraction * 100) if progress.fraction is not None else None,
            "has_source": has_source(ov.metric), "window_end": ov.period_end - timedelta(days=1),
        })
    return rows


def activity_view(activity, now=None):
    state = display_state(activity, now)
    tz = ZoneInfo(activity.timezone)
    local_day = rules.planned_local_date(activity.planned_at_utc, activity.all_day_date, activity.timezone)
    return {
        "a": activity, "state": state, "tone": TONE.get(state, "neutral"), "day": local_day,
        "time": activity.planned_at_utc.astimezone(tz).strftime("%H:%M") if activity.planned_at_utc else None,
        "actual": activity.actual_at_utc.astimezone(tz) if activity.actual_at_utc else None,
    }


def month_grid(activities, month_start, today):
    """Weeks (Mon-Sun) covering the month, each day with its activities in time order."""
    by_day = {}
    unscheduled = []
    for view in activities:
        if view["day"] is None:
            unscheduled.append(view)
        else:
            by_day.setdefault(view["day"], []).append(view)
    for items in by_day.values():
        items.sort(key=lambda v: (v["time"] is not None, v["time"] or ""))
    cal = pycal.Calendar(firstweekday=0)
    weeks = []
    for week in cal.monthdatescalendar(month_start.year, month_start.month):
        weeks.append([{"date": d, "in_month": d.month == month_start.month, "today": d == today, "items": by_day.get(d, [])} for d in week])
    return weeks, unscheduled


def month_bounds(text, fallback):
    try:
        year, month = (int(x) for x in (text or "").split("-"))
        start = date(year, month, 1)
    except (ValueError, TypeError):
        start = fallback.replace(day=1)
    nxt = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    prev = (start - timedelta(days=1)).replace(day=1)
    return start, prev, nxt


def calendar_context(request, campaigns_qs, default_month=None):
    cfg = config()
    now = clock.now()
    today = rules.local_today(now, cfg["timezone"])
    view = request.GET.get("view") if request.GET.get("view") in ("month", "list") else "month"
    month_start, prev_month, next_month = month_bounds(request.GET.get("month"), default_month or today)
    acts = Activity.objects.filter(campaign__in=campaigns_qs).select_related("campaign")
    views = [activity_view(a, now) for a in acts]
    weeks, unscheduled = month_grid(views, month_start, today)
    listed = sorted([v for v in views if v["day"]], key=lambda v: (v["day"], v["time"] or "00:00"))
    return {"view": view, "weeks": weeks, "unscheduled": unscheduled, "listed": listed, "month_start": month_start,
            "prev_month": prev_month, "next_month": next_month, "today": today, "timezone": cfg["timezone"],
            "weekday_names": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}


def alerts():
    out = []
    flagged = Activity.objects.filter(status="planned", campaign__status="active").exclude(review_flag="").select_related("campaign")
    for a in flagged[:10]:
        out.append({"tone": "warn", "owner": a.campaign.name, "text": f"{a.title}: {a.review_flag}", "dialog": f"/ui/activity/{a.pk}"})
    pending = ImportBatch.objects.filter(state="staged")
    for b in pending[:5]:
        out.append({"tone": "warn", "owner": "Sources", "text": f"Import preview for {b.original_name} is waiting for review.", "href": f"/sources/imports/{b.pk}"})
    artist = own_artist()
    if artist:
        through = Observation.objects.filter(entity=artist.entity, active_version__isnull=False).order_by("-period_start").values_list("period_start", flat=True).first()
        f = freshness(through)
        if f["state"] == "stale":
            out.append({"tone": "warn", "owner": "Sources", "text": f"Spotify Audience data is {f['days_old']} days old. Import a fresh export.", "href": "/sources"})
    return out


def active_campaigns():
    return Campaign.objects.filter(status="active").select_related("promoted_object__entity").order_by("start_date")
