from collections import defaultdict
from datetime import date, datetime, time, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Q

from catalogue.models import Entity, PromotedObject
from catalogue.services import create_object, own_artist, parse_date
from core import clock, instance
from core.errors import DomainError, StaleRevision
from core.services import audit, conditional_update, idempotent
from sources.models import MetricDefinition, Source

from . import measurement, registry, rules
from .models import Activity, ActivityOutcome, Campaign, CampaignOutcome, ExecutionEvent, Outcome, OutcomeVersion

TRANSITIONS = {
    ("draft", "active"), ("draft", "cancelled"),
    ("active", "paused"), ("paused", "active"),
    ("active", "completed"), ("active", "cancelled"),
    ("paused", "completed"), ("paused", "cancelled"),
    ("completed", "active"), ("cancelled", "active"),
}
REACTIVATION = {("completed", "active"), ("cancelled", "active")}
CLOCK_SKEW = timedelta(seconds=60)


# Outcomes


def metric_scope_entity(metric, campaign_object):
    if metric.scope_kind == "artist":
        return own_artist().entity
    if campaign_object is None:
        raise DomainError("scope_needs_object", f"{metric.label} measures a {metric.scope_kind}; choose one for this campaign.")
    expected = {"recording": {"recording"}, "event": {"event"}}.get(metric.scope_kind, {metric.scope_kind})
    if campaign_object.kind not in expected:
        raise DomainError(
            "scope_mismatch",
            f"{metric.label} measures a {metric.scope_kind}, but this campaign promotes a {campaign_object.get_kind_display().lower()}.",
            fields={"metric_id": "Scope does not match"},
        )
    return campaign_object.entity


def has_source(metric):
    return Source.objects.filter(provider=metric.provider, state="active").exists()


def _create_outcome_version(name, metric, scope_entity, mode, target, period_start, period_end):
    if mode not in metric.outcome_modes:
        allowed = ", ".join(metric.outcome_modes) or "none"
        raise DomainError("invalid_mode", f"{metric.label} supports: {allowed}.", fields={"mode": "Not valid for this metric"})
    try:
        target = int(target)
    except (TypeError, ValueError):
        raise DomainError("invalid_target", "The target is a whole number.", fields={"target": "Whole number"})
    if target < 0:
        raise DomainError("invalid_target", "The target cannot be negative.", fields={"target": "Not negative"})
    if period_end <= period_start:
        raise DomainError("invalid_window", "The outcome window must end after it starts.")
    tz_name = instance.load()["timezone"]
    outcome = Outcome.objects.create(name=(name or metric.label)[:200], created_at=clock.now())
    return OutcomeVersion.objects.create(
        outcome=outcome,
        version=1,
        metric=metric,
        scope_entity=scope_entity,
        mode=mode,
        target=target,
        period_start=period_start,
        period_end=period_end,
        timezone=tz_name,
        date_basis="utc_day" if metric.grain == "utc_day" else "local_day",
        baseline_rule={"rule": "latest_snapshot_before_start", "max_gap_days": instance.load()["baseline_max_gap_days"]},
        created_at=clock.now(),
    )


def matching_outcomes(metric_id, scope_entity_id, mode, period_start, period_end):
    """Exact contract matches only: same metric, scope, mode and window can be shared."""
    return OutcomeVersion.objects.filter(
        metric_id=metric_id, scope_entity_id=scope_entity_id, mode=mode, period_start=period_start, period_end=period_end
    )


def outcome_today(ov):
    now = clock.now()
    if ov.date_basis == "utc_day":
        return now.date()
    return now.astimezone(ZoneInfo(ov.timezone)).date()


def outcome_progress(ov):
    from sources.services import series

    metric = ov.metric
    if not has_source(metric):
        return measurement.compute(metric.kind, ov.mode, ov.target, ov.period_start, ov.period_end, outcome_today(ov), [], has_source=False)
    start = ov.period_start - timedelta(days=ov.baseline_rule.get("max_gap_days", 7) + 2)
    points = series(ov.scope_entity, metric.pk, purpose="descriptive_derive", start=start, end=ov.period_end)
    if metric.kind == "flow":
        points = [p for p in points if p[0] >= ov.period_start]
    return measurement.compute(
        metric.kind, ov.mode, ov.target, ov.period_start, ov.period_end, outcome_today(ov), points,
        baseline_max_gap_days=ov.baseline_rule.get("max_gap_days", 7),
    )


def describe_outcome(ov):
    verb = {"total": "", "gain": "+", "level": "reach "}[ov.mode]
    return f"{verb}{ov.target:,} {ov.metric.label.lower()}"


# Operational proposals (not evidence-backed tactics)


def preview_operational(data):
    """Dated setup/milestone work derived only from the user's own dates and choices."""
    ctype = data["type"]
    spec = registry.TYPES[ctype]
    start, end = data["start_date"], data["end_date"]
    key_date = data.get("key_date")
    object_label = data.get("object_label") or ""
    metric = data.get("primary_metric")
    items, gaps = [], []

    def clamp(d):
        return min(max(d, start), end)

    def add(key, title, day, kind="operational", purpose="", effort=15, channel="internal", fmt="Task", basis="Campaign constraint"):
        items.append({
            "template_key": key, "title": title, "kind": kind, "date": clamp(day).isoformat(), "time": None,
            "channel": channel, "format": fmt, "purpose": purpose, "effort_minutes": effort,
            "origin": "operational_template", "basis": basis,
        })

    if spec["group"] in ("release", "show") and key_date:
        if not (start <= key_date <= end):
            gaps.append(f"The {spec['anchor'].lower()} ({key_date.isoformat()}) is outside the campaign window.")
        else:
            add("anchor", f"{spec['anchor']}: {object_label}".strip(": "), key_date, kind="milestone", effort=0,
                purpose="Fixed date from the catalogue. It does not move with other work.", basis="Catalogue date")
    elif spec["group"] in ("release", "show"):
        gaps.append(f"No {spec['anchor'].lower()} yet. Add it to place release-relative work.")

    if spec["group"] == "release" and key_date:
        add("links", "Confirm listening links and release destination", key_date - timedelta(days=7),
            purpose="Make sure every post can point to the right place on the day.")
        add("first_week_import", "Import first-week Spotify data", key_date + timedelta(days=8),
            purpose="Export the song and Audience timelines from Spotify for Artists and import them so progress uses real data.")
    if spec["group"] == "show":
        add("ticket_source", "Confirm the ticket link and sales report", start,
            purpose="Ticket progress needs an event-scoped report; likes and clicks are not ticket sales.")
    if spec["group"] == "growth":
        add("baseline", "Import the starting snapshot", start,
            purpose="Progress needs a compatible snapshot from before the start date. Without it, gain stays unknown.")
        mid = start + (end - start) / 2
        add("midpoint_check", "Mid-campaign data check", mid, purpose="Import the latest data and inspect coverage before changing course.")
    add("review", "Review the campaign outcome", end, kind="operational", effort=30,
        purpose="Inspect measured results and limits, then record what to repeat, adapt or stop.")

    if metric is not None and not has_source(metric):
        add("source_setup", f"Set up a source for {metric.label.lower()}", start,
            purpose=f"No connected source measures {metric.label.lower()} yet, so progress will show Needs source.")
        gaps.append(f"{metric.label} has no connected source yet.")
    resources = data.get("resources") or {}
    if "email" in resources.get("channels", []) and not resources.get("email_list_confirmed"):
        gaps.append("Email is selected but no opted-in list is confirmed. Email work is not proposed.")
    assets = resources.get("assets_ready_date")
    if assets and key_date and assets > key_date:
        gaps.append("Assets are ready after the key date. Plan content after the assets date.")
    gaps.insert(0, "No eligible evidence yet, so no evidence-backed tactics are proposed. Add your own activities below.")
    return {"activities": sorted(items, key=lambda i: i["date"]), "gaps": gaps, "template_version": registry.TEMPLATE_VERSION}


# Campaign creation


def _validate_resources(raw):
    raw = raw or {}
    channels = [c for c in raw.get("channels", []) if c in registry.CHANNEL_LABELS]
    out = {
        "channels": channels,
        "audience": str(raw.get("audience", ""))[:300],
        "assets_ready_date": parse_date(raw.get("assets_ready_date"), "assets_ready_date"),
        "budget_minor": None,
        "currency": str(raw.get("currency", "AUD"))[:3].upper(),
        "blackout_dates": [],
        "constraints": str(raw.get("constraints", ""))[:1000],
        "email_list_confirmed": bool(raw.get("email_list_confirmed")),
    }
    budget = raw.get("budget")
    if budget not in (None, ""):
        try:
            out["budget_minor"] = int(round(float(budget) * 100))
        except ValueError:
            raise DomainError("invalid_budget", "Budget is an amount such as 250.", fields={"budget": "Amount"})
        if out["budget_minor"] < 0:
            raise DomainError("invalid_budget", "Budget cannot be negative.", fields={"budget": "Not negative"})
    for d in raw.get("blackout_dates", []) or []:
        if d:
            out["blackout_dates"].append(parse_date(d, "blackout_dates"))
    if "email" in channels and not out["email_list_confirmed"]:
        out["channels"] = [c for c in channels if c != "email"]
        out["email_excluded"] = True
    return out


def _jsonable_resources(res):
    return {k: (v.isoformat() if isinstance(v, date) else [x.isoformat() for x in v] if k == "blackout_dates" else v) for k, v in res.items()}


def resolve_object(ctype, obj_data, tz_name):
    spec = registry.TYPES[ctype]
    if not spec["object_kinds"]:
        return None
    if not obj_data:
        raise DomainError("object_required", f"Choose or add the {spec['object_kinds'][0]} this campaign promotes.", fields={"object": "Required"})
    if obj_data.get("mode") == "existing":
        obj = PromotedObject.objects.select_related("entity").filter(pk=obj_data.get("id")).first()
        if not obj:
            raise DomainError("object_missing", "That item no longer exists.")
        if obj.kind not in spec["object_kinds"]:
            raise DomainError("scope_mismatch", f"A {spec['label'].lower()} campaign promotes a {spec['object_kinds'][0]}.")
        return obj
    kind = spec["object_kinds"][0]
    key_date = parse_date(obj_data.get("key_date"), "key_date")
    metadata = {}
    if kind == "event":
        metadata = {"venue": str(obj_data.get("venue", ""))[:200], "on_sale_date": obj_data.get("on_sale_date") or None,
                    "ticket_url": str(obj_data.get("ticket_url", ""))[:500]}
    return create_object(
        kind,
        obj_data.get("label"),
        key_date=key_date,
        timezone=obj_data.get("timezone") or (tz_name if kind == "event" else ""),
        date_authority="owner_confirmed" if obj_data.get("date_confirmed") and key_date else "unverified",
        metadata=metadata,
    )


def _resolve_outcome(spec, campaign_object, start, end):
    if spec.get("mode") == "existing":
        ov = OutcomeVersion.objects.filter(pk=spec.get("outcome_version_id")).first()
        if not ov:
            raise DomainError("outcome_missing", "That outcome no longer exists.")
        return ov
    metric = MetricDefinition.objects.filter(pk=spec.get("metric_id")).first()
    if not metric:
        raise DomainError("metric_required", "Choose what to measure.", fields={"metric_id": "Required"})
    scope = metric_scope_entity(metric, campaign_object)
    p_start = parse_date(spec.get("period_start"), "period_start") or start
    p_end = parse_date(spec.get("period_end"), "period_end") or (end + timedelta(days=1))
    try:
        target = int(spec.get("target"))
    except (TypeError, ValueError):
        raise DomainError("invalid_target", "The target is a whole number.", fields={"target": "Whole number"})
    existing = matching_outcomes(metric.pk, scope.pk, spec.get("outcome_mode"), p_start, p_end).filter(target=target).first()
    if existing and spec.get("reuse_if_identical", True):
        return existing
    return _create_outcome_version(spec.get("name"), metric, scope, spec.get("outcome_mode"), spec.get("target"), p_start, p_end)


def _activity_time_fields(day, time_text, tz_name):
    if day is None:
        return {"planned_at_utc": None, "all_day_date": None, "planned_local": ""}
    if time_text:
        try:
            at = time.fromisoformat(time_text)
        except ValueError:
            raise DomainError("invalid_time", "Use a time such as 18:00.", fields={"time": "Invalid time"})
        utc = rules.local_to_utc(day, at, tz_name)
        return {"planned_at_utc": utc, "all_day_date": None, "planned_local": f"{day.isoformat()}T{at.strftime('%H:%M')}"}
    return {"planned_at_utc": None, "all_day_date": day, "planned_local": day.isoformat()}


def _clean_activity(data, campaign, tz_name):
    title = str(data.get("title", "")).strip()
    if not title:
        raise DomainError("title_required", "Give the activity a title.", fields={"title": "Required"})
    channel = data.get("channel") or ""
    if channel and channel not in registry.CHANNEL_LABELS:
        raise DomainError("invalid_channel", "Unknown channel.", fields={"channel": "Unknown"})
    if channel == "email" and not campaign.resources.get("email_list_confirmed"):
        raise DomainError("no_email_list", "Email needs an authorised opted-in list on this campaign.", fields={"channel": "No opted-in list"})
    kind = data.get("kind") or ("content" if channel not in ("", "internal") else "operational")
    if kind not in dict(Activity.KINDS):
        raise DomainError("invalid_kind", "Unknown activity type.")
    day = parse_date(data.get("date"), "date")
    fields = _activity_time_fields(day, data.get("time") or None, tz_name)
    try:
        effort = int(data.get("effort_minutes") or 0)
    except ValueError:
        raise DomainError("invalid_effort", "Effort is a number of minutes.", fields={"effort_minutes": "Minutes"})
    checklist = [str(x)[:200] for x in data.get("checklist", []) if str(x).strip()][:20]
    return {
        "title": title[:200], "purpose": str(data.get("purpose", ""))[:2000], "kind": kind, "channel": channel,
        "format": str(data.get("format", ""))[:40], "brief": str(data.get("brief", ""))[:10000], "cta": str(data.get("cta", ""))[:300],
        "checklist": checklist, "effort_minutes": max(0, effort), "timezone": tz_name, **fields,
    }


def create_campaign(payload, idempotency_key):
    return idempotent(idempotency_key, "campaign.create", lambda: _create_campaign(payload))


def _create_campaign(payload):
    artist = own_artist()
    if not artist:
        raise DomainError("no_artist", "Set up the artist first.")
    ctype = payload.get("type")
    if ctype not in registry.TYPES:
        raise DomainError("invalid_type", "Choose a campaign type.", fields={"type": "Required"})
    name = str(payload.get("name", "")).strip()
    if not name:
        raise DomainError("name_required", "Name the campaign.", fields={"name": "Required"})
    start = parse_date(payload.get("start_date"), "start_date")
    end = parse_date(payload.get("end_date"), "end_date")
    if not start or not end:
        raise DomainError("window_required", "Set the campaign start and end dates.", fields={"start_date": "Required", "end_date": "Required"})
    if end < start:
        raise DomainError("invalid_window", "The campaign ends before it starts.", fields={"end_date": "Before start"})
    status = payload.get("status", "active")
    if status not in ("active", "draft"):
        raise DomainError("invalid_status", "New campaigns are active or drafts.")
    tz_name = instance.load()["timezone"]
    obj = resolve_object(ctype, payload.get("object"), tz_name)
    resources = _validate_resources(payload.get("resources"))
    if not payload.get("primary_outcome"):
        raise DomainError("outcome_required", "Choose the primary outcome.", fields={"primary_outcome": "Required"})
    campaign = Campaign.objects.create(
        artist=artist, promoted_object=obj, type=ctype, name=name[:200], start_date=start, end_date=end, timezone=tz_name,
        status=status, resources=_jsonable_resources(resources), created_at=clock.now(),
    )
    primary = _resolve_outcome(payload["primary_outcome"], obj, start, end)
    CampaignOutcome.objects.create(campaign=campaign, outcome_version=primary, role="primary")
    for spec in payload.get("supporting_outcomes", []) or []:
        ov = _resolve_outcome(spec, obj, start, end)
        if ov.pk != primary.pk:
            CampaignOutcome.objects.get_or_create(campaign=campaign, outcome_version=ov, defaults={"role": "supporting"})
    created = []
    for item in payload.get("activities", []) or []:
        if not item.get("selected", True):
            continue
        fields = _clean_activity(item, campaign, tz_name)
        origin = "operational_template" if item.get("origin") == "operational_template" else "manual"
        detail = {"template_key": item.get("template_key"), "template_version": registry.TEMPLATE_VERSION,
                  "basis": item.get("basis") or ("Your schedule" if origin == "manual" else "Campaign constraint")}
        if origin == "operational_template" and item.get("edited"):
            detail["edited_by_owner"] = True
        activity = Activity.objects.create(campaign=campaign, origin=origin, origin_detail=detail, created_at=clock.now(), **fields)
        ActivityOutcome.objects.create(activity=activity, outcome_version=primary)
        created.append(str(activity.pk))
    audit("campaign", campaign.pk, "create", {"type": ctype, "status": status, "activities": len(created), "primary_outcome": str(primary.pk)})
    return {"campaign_id": str(campaign.pk), "activities": created, "primary_outcome_version_id": str(primary.pk)}


# Activities


def _campaign_allows_work(campaign):
    if campaign.status in ("completed", "cancelled"):
        raise DomainError("campaign_closed", f"This campaign is {campaign.status}. Reactivate it to change its work.", status=409)


def add_activity(campaign_id, data, idempotency_key):
    def run():
        campaign = Campaign.objects.get(pk=campaign_id)
        _campaign_allows_work(campaign)
        fields = _clean_activity(data, campaign, campaign.timezone)
        activity = Activity.objects.create(campaign=campaign, origin="manual", origin_detail={"basis": "Your schedule"}, created_at=clock.now(), **fields)
        for ov_id in data.get("outcome_version_ids") or [link.outcome_version_id for link in campaign.outcome_links.filter(role="primary")]:
            if campaign.outcome_links.filter(outcome_version_id=ov_id).exists():
                ActivityOutcome.objects.get_or_create(activity=activity, outcome_version_id=ov_id)
        audit("activity", activity.pk, "create", {"campaign": str(campaign.pk), "title": activity.title})
        return {"activity_id": str(activity.pk), "revision": activity.revision, "warnings": capacity_warnings([activity])}

    return idempotent(idempotency_key, f"activity.create:{campaign_id}", run)


def update_activity(activity_id, expected_revision, data, idempotency_key):
    def run():
        activity = Activity.objects.select_related("campaign").get(pk=activity_id)
        _campaign_allows_work(activity.campaign)
        fields = {}
        for key, limit in [("title", 200), ("purpose", 2000), ("brief", 10000), ("cta", 300), ("format", 40)]:
            if key in data:
                fields[key] = str(data[key])[:limit]
        if "title" in fields and not fields["title"].strip():
            raise DomainError("title_required", "Give the activity a title.", fields={"title": "Required"})
        if "checklist" in data:
            fields["checklist"] = [str(x)[:200] for x in data["checklist"] if str(x).strip()][:20]
        if "effort_minutes" in data:
            fields["effort_minutes"] = max(0, int(data["effort_minutes"] or 0))
        if activity.origin == "operational_template" and any(k in fields for k in ("title", "purpose")):
            fields["origin_detail"] = {**activity.origin_detail, "edited_by_owner": True}
        revision = conditional_update(Activity, activity.pk, expected_revision, what="activity", **fields)
        audit("activity", activity.pk, "edit", {"fields": sorted(fields)}, revision=revision)
        return {"activity_id": str(activity.pk), "revision": revision}

    return idempotent(idempotency_key, f"activity.edit:{activity_id}", run)


def reschedule(activity_id, expected_revision, day_text, time_text, idempotency_key):
    def run():
        activity = Activity.objects.select_related("campaign").get(pk=activity_id)
        _campaign_allows_work(activity.campaign)
        if activity.status != "planned":
            raise DomainError("reopen_first", f"This activity is {activity.status}. Reopen it before changing its date.", status=409)
        day = parse_date(day_text, "date")
        fields = _activity_time_fields(day, time_text or None, activity.timezone)
        before = activity.planned_local
        detail = {**activity.origin_detail, "basis": "Your schedule", "previous_basis": activity.origin_detail.get("basis")}
        revision = conditional_update(Activity, activity.pk, expected_revision, what="activity", origin_detail=detail, review_flag="", **fields)
        audit("activity", activity.pk, "reschedule", {"from": before, "to": fields["planned_local"]}, revision=revision)
        activity.refresh_from_db()
        return {"activity_id": str(activity.pk), "revision": revision, "warnings": capacity_warnings([activity])}

    return idempotent(idempotency_key, f"activity.schedule:{activity_id}", run)


def parse_local_datetime(text, tz_name):
    try:
        naive = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        raise DomainError("invalid_datetime", "Use a valid date and time.", fields={"actual_at": "Invalid"})
    if naive.tzinfo is not None:
        return naive.astimezone(ZoneInfo("UTC"))
    return rules.local_to_utc(naive.date(), naive.time(), tz_name)


def execute(activity_id, expected_revision, action, idempotency_key, actual_at=None, url="", notes="", reason=""):
    def run():
        activity = Activity.objects.select_related("campaign").get(pk=activity_id)
        _campaign_allows_work(activity.campaign)
        if activity.campaign.status == "draft":
            raise DomainError("campaign_draft", "Activate the campaign before recording execution.", status=409)
        if activity.revision != expected_revision:
            raise StaleRevision("activity")
        prior = activity.status
        now = clock.now()
        fields = {}
        event = {"actual_at": None, "url": "", "reason": ""}
        if action == "complete":
            if prior != "planned":
                raise DomainError("invalid_transition", f"This activity is already {prior}.", status=409)
            when = parse_local_datetime(actual_at, activity.timezone) if actual_at else now
            if when > now + CLOCK_SKEW:
                raise DomainError("future_completion", "Completion time cannot be in the future.", fields={"actual_at": "In the future"})
            link = (url or "").strip()
            if link:
                parsed = urlparse(link)
                if parsed.scheme not in ("http", "https") or not parsed.netloc:
                    raise DomainError("invalid_url", "Use a full https:// link.", fields={"url": "Invalid link"})
            fields = {"status": "completed", "actual_at_utc": when, "actual_url": link[:500], "execution_notes": str(notes)[:2000]}
            event.update(actual_at=when, url=link[:500], reason=str(notes)[:2000])
        elif action in ("skip", "cancel"):
            if prior != "planned":
                raise DomainError("invalid_transition", f"This activity is already {prior}.", status=409)
            reason_text = (reason or "").strip()
            if not reason_text:
                raise DomainError("reason_required", f"Say why it was {'skipped' if action == 'skip' else 'cancelled'}.", fields={"reason": "Required"})
            fields = {"status": "skipped" if action == "skip" else "cancelled"}
            event["reason"] = reason_text[:2000]
        elif action == "reopen":
            if prior == "planned":
                raise DomainError("invalid_transition", "This activity is already open.", status=409)
            fields = {"status": "planned", "actual_at_utc": None, "actual_url": "", "execution_notes": ""}
            event["reason"] = (reason or "").strip()[:2000]
        else:
            raise DomainError("invalid_action", "Unknown action.")
        revision = conditional_update(Activity, activity.pk, expected_revision, what="activity", **fields)
        ExecutionEvent.objects.create(
            activity=activity, prior_state=prior, new_state=fields["status"], actual_at=event["actual_at"], url=event["url"],
            reason=event["reason"], recorded_at=now, idempotency_key=idempotency_key,
        )
        audit("activity", activity.pk, f"execute.{action}", {"from": prior, "to": fields["status"]}, revision=revision)
        return {"activity_id": str(activity.pk), "revision": revision, "status": fields["status"]}

    return idempotent(idempotency_key, f"activity.execute:{activity_id}", run)


# Campaign lifecycle


def set_status(campaign_id, expected_revision, new_status, reason, idempotency_key):
    def run():
        campaign = Campaign.objects.get(pk=campaign_id)
        if campaign.revision != expected_revision:
            raise StaleRevision("campaign")
        if (campaign.status, new_status) not in TRANSITIONS:
            raise DomainError("invalid_transition", f"A {campaign.status} campaign cannot become {new_status}.", status=409)
        text = (reason or "").strip()
        if (campaign.status, new_status) in REACTIVATION and not text:
            raise DomainError("reason_required", "Say why you are reactivating this campaign.", fields={"reason": "Required"})
        revision = conditional_update(Campaign, campaign.pk, expected_revision, what="campaign", status=new_status)
        audit("campaign", campaign.pk, "status", {"from": campaign.status, "to": new_status, "reason": text[:500]}, revision=revision)
        return {"campaign_id": str(campaign.pk), "revision": revision, "status": new_status}

    return idempotent(idempotency_key, f"campaign.status:{campaign_id}", run)


def update_campaign(campaign_id, expected_revision, data, idempotency_key):
    def run():
        campaign = Campaign.objects.get(pk=campaign_id)
        _campaign_allows_work(campaign)
        fields = {}
        if "name" in data and str(data["name"]).strip():
            fields["name"] = str(data["name"]).strip()[:200]
        start = parse_date(data.get("start_date"), "start_date") if data.get("start_date") else campaign.start_date
        end = parse_date(data.get("end_date"), "end_date") if data.get("end_date") else campaign.end_date
        if end < start:
            raise DomainError("invalid_window", "The campaign ends before it starts.", fields={"end_date": "Before start"})
        dates_changed = (start, end) != (campaign.start_date, campaign.end_date)
        if dates_changed:
            fields.update(start_date=start, end_date=end)
        if "resources" in data:
            fields["resources"] = _jsonable_resources(_validate_resources(data["resources"]))
        revision = conditional_update(Campaign, campaign.pk, expected_revision, what="campaign", **fields)
        flagged = 0
        if dates_changed:
            flagged = flag_work_for_date_change(
                campaign_id=campaign.pk,
                reason=f"Campaign window changed from {campaign.start_date}–{campaign.end_date} to {start}–{end}. Check this date.",
            )
        audit("campaign", campaign.pk, "edit", {"fields": sorted(fields), "flagged": flagged}, revision=revision)
        return {"campaign_id": str(campaign.pk), "revision": revision, "flagged_activities": flagged}

    return idempotent(idempotency_key, f"campaign.edit:{campaign_id}", run)


def flag_work_for_date_change(reason, object_id=None, campaign_id=None):
    """Approved work is flagged for review, never moved silently."""
    qs = Activity.objects.filter(status="planned")
    if object_id:
        qs = qs.filter(campaign__promoted_object_id=object_id)
    if campaign_id:
        qs = qs.filter(campaign_id=campaign_id)
    from django.db.models import F

    return qs.update(review_flag=reason[:300], revision=F("revision") + 1)


@transaction.atomic
def link_outcome(campaign_id, outcome_version_id, role="supporting"):
    campaign = Campaign.objects.get(pk=campaign_id)
    ov = OutcomeVersion.objects.get(pk=outcome_version_id)
    link, created = CampaignOutcome.objects.get_or_create(campaign=campaign, outcome_version=ov, defaults={"role": role})
    if created:
        audit("campaign", campaign.pk, "link_outcome", {"outcome_version": str(ov.pk), "role": role})
    return link


def add_supporting_outcome(campaign_id, spec, idempotency_key):
    def run():
        campaign = Campaign.objects.select_related("promoted_object__entity").get(pk=campaign_id)
        _campaign_allows_work(campaign)
        ov = _resolve_outcome(spec, campaign.promoted_object, campaign.start_date, campaign.end_date)
        link = link_outcome(campaign.pk, ov.pk, "supporting")
        return {"outcome_version_id": str(ov.pk), "role": link.role}

    return idempotent(idempotency_key, f"campaign.outcome:{campaign_id}", run)


# Reads


def display_state(activity, now=None):
    return rules.derived_state(activity.status, activity.planned_at_utc, activity.all_day_date, now or clock.now(), activity.timezone)


def capacity_warnings(new_activities):
    """Shared weekly labour across active campaigns. Stage 1 warns; it never deletes or moves work."""
    limit = instance.load()["weekly_capacity_minutes"]
    weeks = set()
    for a in new_activities:
        d = rules.planned_local_date(a.planned_at_utc, a.all_day_date, a.timezone)
        if d:
            weeks.add(d.isocalendar()[:2])
    if not weeks:
        return []
    totals = defaultdict(int)
    for a in Activity.objects.filter(status="planned", campaign__status="active").exclude(planned_at_utc__isnull=True, all_day_date__isnull=True):
        d = rules.planned_local_date(a.planned_at_utc, a.all_day_date, a.timezone)
        wk = d.isocalendar()[:2]
        if wk in weeks:
            totals[wk] += a.effort_minutes
    return [
        {"code": "capacity_exceeded", "message": f"Week {w[1]} of {w[0]} has {m // 60}h {m % 60}m planned against your {limit // 60}h weekly capacity."}
        for w, m in sorted(totals.items()) if m > limit
    ]


def deduplicated_outcomes(campaigns=None):
    """One row per outcome contract with all linked campaigns. Overlap is not attribution."""
    links = CampaignOutcome.objects.select_related("outcome_version__metric", "outcome_version__scope_entity", "outcome_version__outcome", "campaign")
    if campaigns is not None:
        links = links.filter(campaign__in=campaigns)
    grouped = {}
    for link in links.order_by("outcome_version__period_start"):
        entry = grouped.setdefault(link.outcome_version_id, {"ov": link.outcome_version, "campaigns": []})
        entry["campaigns"].append((link.campaign, link.role))
    return list(grouped.values())


def due_work(now=None, limit=20):
    now = now or clock.now()
    acts = Activity.objects.filter(status="planned", campaign__status="active").select_related("campaign").filter(
        Q(planned_at_utc__isnull=False) | Q(all_day_date__isnull=False)
    )
    rows = []
    for a in acts:
        state = display_state(a, now)
        if state in ("Overdue", "Due today"):
            rows.append((0 if state == "Overdue" else 1, a.planned_at_utc or datetime.combine(a.all_day_date, time.min, tzinfo=ZoneInfo(a.timezone)), a, state))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [(a, s) for _, _, a, s in rows[:limit]]


def upcoming_milestones(now=None, days=21):
    now = now or clock.now()
    tz_name = instance.load()["timezone"]
    today = rules.local_today(now, tz_name)
    return list(
        Activity.objects.filter(kind="milestone", status="planned", campaign__status="active", all_day_date__gte=today,
                                all_day_date__lte=today + timedelta(days=days)).select_related("campaign").order_by("all_day_date")
    )


def object_entity(entity_id):
    return Entity.objects.get(pk=entity_id)
