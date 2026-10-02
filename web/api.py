"""JSON mutation API. Every POST needs CSRF and an Idempotency-Key; responses use {data, revision, warnings} or {error}."""
import json
import logging
from datetime import timedelta
from functools import wraps

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from campaigns import services as campaigns
from campaigns.models import Campaign
from catalogue import services as catalogue
from catalogue.models import PromotedObject
from core import instance
from core.errors import DomainError
from core.services import audit, check_idempotency_key, idempotent
from sources import services as sources

log = logging.getLogger(__name__)


class _DryRun(Exception):
    pass


def api(fn):
    @require_POST
    @wraps(fn)
    def view(request, *args, **kwargs):
        try:
            key = check_idempotency_key(request.headers.get("Idempotency-Key"))
            if request.content_type == "application/json":
                try:
                    body = json.loads(request.body or b"{}")
                except ValueError:
                    raise DomainError("invalid_json", "The request body is not valid JSON.")
                if not isinstance(body, dict):
                    raise DomainError("invalid_json", "The request body must be an object.")
            else:
                body = request.POST
            data = fn(request, body, key, *args, **kwargs) or {}
        except DomainError as exc:
            return JsonResponse({"error": exc.as_dict()}, status=exc.status)
        except ObjectDoesNotExist:
            return JsonResponse({"error": {"code": "not_found", "message": "That record no longer exists.", "fields": {}, "retryable": False}}, status=404)
        except Exception:
            log.exception("Unhandled API error in %s", fn.__name__)
            return JsonResponse({"error": {"code": "server_error", "message": "Something went wrong. Nothing was changed.", "fields": {}, "retryable": True}}, status=500)
        warnings = data.pop("warnings", []) if isinstance(data, dict) else []
        return JsonResponse({"data": data, "revision": data.get("revision") if isinstance(data, dict) else None, "warnings": warnings})

    return view


def _revision(body, name="revision"):
    try:
        return int(body.get(name))
    except (TypeError, ValueError):
        raise DomainError("revision_required", "Reload and try again.", status=409)


# Imports

@api
def import_upload(request, body, key):
    upload = request.FILES.get("file")
    if upload is None:
        raise DomainError("file_required", "Choose a CSV file.", fields={"file": "Required"})
    if upload.size > 5 * 1024 * 1024 + 1:
        raise DomainError("file_too_large", "Files up to 5 MB are supported.", fields={"file": "Too large"})
    raw = upload.read()

    def run():
        batch = sources.preview_upload(raw, upload.name)
        return {"batch_id": str(batch.pk), "redirect": reverse("import_batch", args=[batch.pk])}

    return idempotent(key, "import.preview", run)


@api
def import_mapping(request, body, key, batch_id):
    def run():
        if body.get("target") == "new":
            batch = sources.set_mapping(batch_id, _revision(body), new_recording_label=(body.get("new_label") or "").strip() or None)
        else:
            batch = sources.set_mapping(batch_id, _revision(body), entity_id=body.get("entity_id") or None)
        return {"batch_id": str(batch.pk), "revision": batch.preview_revision}

    return idempotent(key, f"import.map:{batch_id}", run)


@api
def import_approve(request, body, key, batch_id):
    def run():
        batch = sources.approve_conflicts(batch_id, _revision(body), "all", body.get("reason", ""))
        return {"batch_id": str(batch.pk), "revision": batch.preview_revision}

    return idempotent(key, f"import.approve:{batch_id}", run)


@api
def import_commit(request, body, key, batch_id):
    return sources.commit(batch_id, _revision(body), key)


@api
def import_undo(request, body, key, batch_id):
    return sources.undo(batch_id, body.get("reason", ""), key)


@api
def import_cancel(request, body, key, batch_id):
    def run():
        sources.cancel_preview(batch_id)
        return {"batch_id": str(batch_id), "redirect": reverse("sources")}

    return idempotent(key, f"import.cancel:{batch_id}", run)


# Campaigns

def _campaign_payload(body):
    payload = body.get("campaign")
    if not isinstance(payload, dict):
        raise DomainError("invalid_payload", "Campaign details are missing.")
    return payload


@api
def campaign_preview(request, body, key):
    """Validate the whole draft in a rolled-back transaction, then return operational proposals. Persists nothing."""
    payload = _campaign_payload(body)
    try:
        with transaction.atomic():
            campaigns._create_campaign({**payload, "activities": []})
            raise _DryRun
    except _DryRun:
        pass
    from campaigns import registry
    from sources.models import MetricDefinition

    ctype = payload["type"]
    obj_data = payload.get("object") or {}
    key_date, label = None, ""
    if obj_data.get("mode") == "existing":
        obj = PromotedObject.objects.select_related("entity").get(pk=obj_data.get("id"))
        key_date, label = obj.key_date, obj.label
    elif obj_data:
        key_date, label = catalogue.parse_date(obj_data.get("key_date"), "key_date"), obj_data.get("label", "")
    metric = MetricDefinition.objects.filter(pk=(payload.get("primary_outcome") or {}).get("metric_id")).first()
    resources = campaigns._validate_resources(payload.get("resources"))
    preview = campaigns.preview_operational({
        "type": ctype, "start_date": catalogue.parse_date(payload["start_date"]), "end_date": catalogue.parse_date(payload["end_date"]),
        "key_date": key_date, "object_label": label, "primary_metric": metric, "resources": resources,
    })
    evidence = {"activities": [], "gaps": [], "llm_used": False}
    if body.get("use_evidence"):
        from intelligence.synthesis import generate_evidence_activities

        evidence = generate_evidence_activities(
            {**payload, "key_date": key_date.isoformat() if key_date else None, "timezone": instance.load()["timezone"], "resources": resources},
            preview,
        )
        preview = {
            **preview,
            "activities": preview["activities"] + evidence.get("activities", []),
            "gaps": evidence.get("gaps", preview.get("gaps", [])),
            "planning_notes": evidence.get("planning_notes") or [],
            "composition": evidence.get("composition") or {},
            "evidence_bundle": evidence.get("bundle"),
            "llm_used": evidence.get("llm_used"),
            "recommendation_id": evidence.get("recommendation_id"),
        }
    html = render_to_string("web/dialogs/_campaign_review.html", {
        "preview": preview, "payload": payload, "type_label": registry.type_label(ctype), "metric": metric,
        "channels": registry.CHANNELS, "resources": resources, "object_label": label,
    }, request=request)
    return {"html": html, "template_version": preview["template_version"], "evidence": evidence}


@api
def campaign_create(request, body, key):
    result = campaigns.create_campaign(_campaign_payload(body), key)
    return {**result, "redirect": reverse("campaign", args=[result["campaign_id"]])}


@api
def campaign_update(request, body, key, campaign_id):
    data = {k: body.get(k) for k in ("name", "start_date", "end_date") if body.get(k)}
    return campaigns.update_campaign(campaign_id, _revision(body), data, key)


@api
def campaign_status(request, body, key, campaign_id):
    return campaigns.set_status(campaign_id, _revision(body), body.get("status"), body.get("reason", ""), key)


@api
def campaign_outcome(request, body, key, campaign_id):
    if body.get("outcome_version_id"):
        def run():
            Campaign.objects.get(pk=campaign_id)
            link = campaigns.link_outcome(campaign_id, body["outcome_version_id"])
            return {"outcome_version_id": str(link.outcome_version_id)}

        return idempotent(key, f"campaign.link:{campaign_id}", run)
    last_day = catalogue.parse_date(body.get("last_day"), "last_day")
    spec = {"mode": "new", "metric_id": body.get("metric_id"), "outcome_mode": body.get("outcome_mode"), "target": body.get("target"),
            "period_start": body.get("period_start") or None,
            "period_end": (last_day + timedelta(days=1)).isoformat() if last_day else None}
    return campaigns.add_supporting_outcome(campaign_id, spec, key)


@api
def activity_create(request, body, key, campaign_id):
    data = {k: body.get(k) for k in ("title", "date", "time", "channel", "format", "purpose", "brief", "cta", "effort_minutes", "kind")}
    data["checklist"] = [line for line in str(body.get("checklist") or "").splitlines()]
    return campaigns.add_activity(campaign_id, data, key)


@api
def activity_update(request, body, key, activity_id):
    from campaigns.models import Activity

    activity = Activity.objects.get(pk=activity_id)
    rev = _revision(body)
    data = {k: body.get(k) for k in ("title", "purpose", "brief", "cta", "format", "effort_minutes") if k in body}
    if "checklist" in body:
        data["checklist"] = str(body.get("checklist") or "").splitlines()
    new_day, new_time = body.get("date") or "", body.get("time") or ""
    current_day = activity.planned_local[:10]
    current_time = activity.planned_local[11:16] if "T" in activity.planned_local else ""
    schedule_changed = "date" in body and (new_day, new_time) != (current_day, current_time)
    with transaction.atomic():
        result = campaigns.update_activity(activity_id, rev, data, key)
        if schedule_changed:
            moved = campaigns.reschedule(activity_id, result["revision"], new_day or None, new_time or None, f"{key}:schedule")
            result = {**result, "revision": moved["revision"], "warnings": moved.get("warnings", [])}
    return result


@api
def activity_execute(request, body, key, activity_id):
    return campaigns.execute(activity_id, _revision(body), body.get("action"), key, actual_at=body.get("actual_at") or None,
                             url=body.get("url", ""), notes=body.get("notes", ""), reason=body.get("reason", ""))


# Catalogue and settings

@api
def object_create(request, body, key):
    def run():
        kind = body.get("kind")
        key_date = catalogue.parse_date(body.get("key_date"), "key_date")
        tz_name = instance.load()["timezone"] if kind == "event" else ""
        obj = catalogue.create_object(kind, body.get("label"), key_date=key_date, timezone=tz_name,
                                      date_authority="owner_confirmed" if body.get("date_confirmed") else "unverified")
        if body.get("spotify_url") or body.get("isrc"):
            catalogue.update_object(obj.pk, obj.revision, spotify_url=body.get("spotify_url") or None, isrc=body.get("isrc") or None)
        return {"object_id": str(obj.pk)}

    return idempotent(key, "object.create", run)


@api
def object_update(request, body, key, object_id):
    def run():
        obj = catalogue.update_object(
            object_id, _revision(body), label=body.get("label"), key_date=catalogue.parse_date(body.get("key_date"), "key_date"),
            date_confirmed=bool(body.get("date_confirmed")), spotify_url=body.get("spotify_url") or None, isrc=body.get("isrc") or None,
        )
        return {"object_id": str(obj.pk), "revision": obj.revision, "identity_state": obj.identity_state}

    return idempotent(key, f"object.update:{object_id}", run)


@api
def settings_update(request, body, key):
    def run():
        artist = catalogue.own_artist()
        changes = {}
        label = str(body.get("artist_label") or "").strip()
        if label and label != artist.label:
            from catalogue.models import Entity

            Entity.objects.filter(pk=artist.pk).update(label=label[:200])
            changes["artist_label"] = label[:200]
        if body.get("spotify_artist_url"):
            catalogue.set_artist_spotify(artist, body["spotify_artist_url"])
        if body.get("timezone"):
            changes["timezone"] = instance.validate_timezone(str(body["timezone"]).strip())
        for name, lo, hi in [("weekly_capacity_minutes", 0, 10080), ("stale_after_days", 1, 90)]:
            if body.get(name) not in (None, ""):
                try:
                    value = int(body[name])
                except (TypeError, ValueError):
                    raise DomainError("invalid_number", "Use a whole number.", fields={name: "Whole number"})
                if not lo <= value <= hi:
                    raise DomainError("out_of_range", f"Use a value from {lo} to {hi}.", fields={name: "Out of range"})
                changes[name] = value
        if body.get("default_post_time"):
            from datetime import time

            try:
                changes["default_post_time"] = time.fromisoformat(body["default_post_time"]).strftime("%H:%M")
            except ValueError:
                raise DomainError("invalid_time", "Use a time such as 18:00.", fields={"default_post_time": "Invalid"})
        if changes:
            instance.update(**changes)
            audit("instance", instance.load()["instance_id"], "settings", changes)
        return {"changed": sorted(changes)}

    return idempotent(key, "settings.update", run)


@api
def peer_discover_lastfm(request, body, key):
    from context.services import discover_lastfm_similar

    artist = (body.get("artist") or "Opal Season").strip()
    limit = min(int(body.get("limit") or 30), 50)

    def run():
        return discover_lastfm_similar(artist, limit=limit)

    return idempotent(key, "peer.discover_lastfm", run)


@api
def peer_promote(request, body, key):
    from context.services import promote_candidate

    def run():
        peer = promote_candidate(
            body["candidate_id"],
            instagram_username=body.get("instagram_username") or "",
            musicbrainz_mbid=body.get("musicbrainz_mbid") or "",
            notes=body.get("notes") or "",
        )
        return {"peer_id": str(peer.pk), "redirect": "/peers"}

    return idempotent(key, "peer.promote", run)


@api
def peer_reject(request, body, key):
    from context.services import reject_candidate

    def run():
        reject_candidate(body["candidate_id"], body.get("reason") or "")
        return {"redirect": "/peers"}

    return idempotent(key, "peer.reject", run)


@api
def musicbrainz_search(request, body, key):
    from sources import musicbrainz

    def run():
        return musicbrainz.search_artists(body.get("artist", "").strip())

    return idempotent(key, "musicbrainz.search", run)


@api
def ask_question(request, body, key):
    from intelligence.ask_service import answer_question

    question = (body.get("question") or "").strip()
    if not question:
        raise DomainError("question_required", "Enter a question.", fields={"question": "Required"})

    def run():
        ex = answer_question(question, body.get("scope") or {})
        return {"exchange_id": str(ex.pk), "answer": ex.answer, "redirect": "/ask"}

    return idempotent(key, "ask.question", run)


@api
@api
def experiment_create(request, body, key, campaign_id):
    from intelligence.experiments_service import create_experiment

    return create_experiment(campaign_id, body, key)


@api
def experiment_approve(request, body, key, experiment_id):
    from intelligence.experiments_service import approve_experiment

    return approve_experiment(experiment_id, key)


@api
def experiment_start(request, body, key, experiment_id):
    from intelligence.experiments_service import start_experiment

    return start_experiment(experiment_id, key)


@api
def experiment_review(request, body, key, experiment_id):
    from intelligence.experiments_service import review_experiment

    return review_experiment(experiment_id, body, key)


@api
def adaptation_decide(request, body, key, proposal_id):
    from intelligence.adaptations import decide

    action = body.get("action")
    if action not in ("accept", "reject"):
        raise DomainError("invalid_action", "Choose accept or reject.")
    return decide(proposal_id, action, key)


@api
def backup_now(request, body, key):
    from core.backup import create_backup

    dest, manifest = create_backup("manual")
    audit("backup", dest.name, "create", {"integrity": manifest["integrity"], "files": len(manifest["files"])})
    return {"backup": dest.name, "integrity": manifest["integrity"]}
