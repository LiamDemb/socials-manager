"""Resolve campaign planning context from payload (no persistence)."""
from datetime import date

from campaigns import registry
from campaigns.services import metric_scope_entity
from catalogue.models import PromotedObject
from catalogue.services import own_artist, parse_date
from sources.models import MetricDefinition

from .contracts import campaign_group


def resolve_planning_context(payload: dict) -> dict:
    ctype = payload.get("type") or ""
    resources = payload.get("resources") or {}
    primary = payload.get("primary_outcome") or {}
    metric = MetricDefinition.objects.filter(pk=primary.get("metric_id")).first()
    obj = None
    obj_data = payload.get("object") or {}
    if obj_data.get("mode") == "existing" and obj_data.get("id"):
        obj = PromotedObject.objects.select_related("entity").filter(pk=obj_data["id"]).first()
    key_date = payload.get("key_date")
    if isinstance(key_date, str):
        key_date = parse_date(key_date, "key_date")
    start = parse_date(payload.get("start_date"), "start_date")
    end = parse_date(payload.get("end_date"), "end_date")
    scope_entities = []
    artist = own_artist()
    if artist:
        scope_entities.append(artist.entity)
    if obj:
        scope_entities.append(obj.entity)
    if metric and start and end:
        try:
            scope_entities.append(metric_scope_entity(metric, obj))
        except Exception:
            pass
    # unique entities
    seen = set()
    entities = []
    for e in scope_entities:
        if e and e.pk not in seen:
            seen.add(e.pk)
            entities.append(e)
    blackouts = []
    for d in resources.get("blackout_dates") or []:
        if isinstance(d, date):
            blackouts.append(d)
        elif d:
            blackouts.append(parse_date(d, "blackout_date"))
    assets = resources.get("assets_ready_date")
    assets_date = parse_date(assets, "assets_ready_date") if assets else None
    unused = []
    if resources.get("audience") and not resources.get("audience_used"):
        unused.append("audience")
    if resources.get("constraints"):
        unused.append("constraints_note_only")
    if resources.get("budget_minor") is None and not resources.get("budget"):
        unused.append("budget")
    supporting_metric_ids = []
    supporting_labels = []
    for spec in payload.get("supporting_outcomes") or []:
        sm = MetricDefinition.objects.filter(pk=spec.get("metric_id")).first()
        if sm:
            supporting_metric_ids.append(sm.pk)
            supporting_labels.append(sm.label)
    return {
        "campaign_type": ctype,
        "campaign_group": campaign_group(ctype),
        "campaign_name": (payload.get("name") or "")[:200],
        "object": obj,
        "object_label": obj.label if obj else (obj_data.get("label") or ""),
        "key_date": key_date,
        "start_date": start,
        "end_date": end,
        "timezone": payload.get("timezone") or "Australia/Perth",
        "primary_metric": metric,
        "primary_metric_id": metric.pk if metric else "",
        "scope_entities": entities,
        "channels": resources.get("channels") or ["instagram"],
        "audience": resources.get("audience") or "",
        "assets_ready_date": assets_date,
        "blackout_dates": blackouts,
        "email_list_confirmed": bool(resources.get("email_list_confirmed")),
        "budget_minor": resources.get("budget_minor"),
        "constraints": resources.get("constraints") or "",
        "unused_inputs_disclosed": unused,
        "type_label": registry.type_label(ctype),
        "supporting_metric_ids": supporting_metric_ids,
        "supporting_outcome_labels": supporting_labels,
    }
