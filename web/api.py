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
    from context.services import discover_lastfm_similar, discovery_seed_artist

    artist = (body.get("artist") or discovery_seed_artist()).strip()
    limit = min(int(body.get("limit") or 30), 50)

    def run():
        result = discover_lastfm_similar(artist, limit=limit)
        warnings = []
        if result.get("state") == "error":
            warnings.append({"message": result.get("error") or "Last.fm discovery failed."})
        elif not result.get("similar"):
            warnings.append({"message": f"No similar artists returned for “{artist}”. Try another seed artist."})
        elif result.get("candidates_created", 0) == 0:
            warnings.append({"message": "No new candidates (they may already be listed)."})
        payload = {**result, "redirect": "/peers"}
        if warnings:
            payload["warnings"] = warnings
        return payload

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
            peer_role=body.get("peer_role") or "unresolved",
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
def peer_create(request, body, key):
    from context.services import create_manual_peer

    def run():
        peer = create_manual_peer(
            body.get("label") or "",
            instagram_username=body.get("instagram_username") or "",
            peer_role=body.get("peer_role") or "unresolved",
            notes=body.get("notes") or "",
        )
        return {"peer_id": str(peer.pk), "redirect": "/peers"}

    return idempotent(key, "peer.create", run)


@api
def peer_update(request, body, key):
    from context.services import update_peer_profile

    def run():
        peer = update_peer_profile(
            body["peer_id"],
            instagram_username=body.get("instagram_username"),
            peer_role=body.get("peer_role"),
            label=body.get("label"),
            collection_paused=body.get("collection_paused"),
        )
        return {"peer_id": str(peer.pk), "redirect": "/peers"}

    return idempotent(key, "peer.update", run)


@api
def inspiration_save(request, body, key):
    from context.inspiration_services import save_peer_media

    def run():
        ref = save_peer_media(body["peer_media_id"], note=body.get("note") or "")
        return {"reference_id": str(ref.pk), "redirect": body.get("redirect") or "/inspiration"}

    return idempotent(key, "inspiration.save", run)


@api
def inspiration_unsave(request, body, key):
    from context.inspiration_services import unsave_reference

    def run():
        unsave_reference(body["reference_id"])
        return {"redirect": body.get("redirect") or "/inspiration"}

    return idempotent(key, "inspiration.unsave", run)


@api
def inspiration_manual(request, body, key):
    from context.inspiration_services import add_manual_reference

    def run():
        ref = add_manual_reference(
            body.get("title") or "",
            body.get("url") or "",
            note=body.get("note") or "",
            scope=body.get("scope") or "global",
            scope_ref=body.get("scope_ref") or "",
        )
        return {"reference_id": str(ref.pk), "redirect": body.get("redirect") or "/inspiration"}

    return idempotent(key, "inspiration.manual", run)


@api
def activity_attach_reference(request, body, key, activity_id):
    from context.inspiration_services import attach_reference, save_peer_media

    def run():
        ref_id = body.get("reference_id")
        if body.get("peer_media_id") and not ref_id:
            ref = save_peer_media(body["peer_media_id"], note=body.get("note") or "")
            ref_id = str(ref.pk)
        attach_reference(activity_id, ref_id, origin=body.get("origin") or "owner_attach", note=body.get("note") or "")
        return {"redirect": f"/ui/activity/{activity_id}"}

    return idempotent(key, f"activity.attach_ref.{activity_id}", run)


@api
def inspiration_recommend(request, body, key):
    from campaigns.models import Activity
    from intelligence.inspiration_service import recommend_for_activity

    def run():
        activity = None
        if body.get("activity_id"):
            activity = Activity.objects.get(pk=body["activity_id"])
        return recommend_for_activity(
            activity=activity,
            context=body.get("context") or {},
            mode=body.get("mode") or "best_fit",
            limit=min(int(body.get("limit") or 5), 5),
        )

    return idempotent(key, "inspiration.recommend", run)


@api
def media_process(request, body, key):
    from context.media_pack import ensure_media_pack

    def run():
        return ensure_media_pack(body["peer_media_id"], reprocess=bool(body.get("reprocess")))

    return idempotent(key, "media.process", run)


@api
def media_inspect(request, body, key):
    from context.media_inspect import inspect_peer_media

    def run():
        return inspect_peer_media(body["peer_media_id"])

    return idempotent(key, "media.inspect", run)


@api
def media_upload(request, body, key):
    from context.media_acquire import reject_extension_mismatch, sniff_image_mime
    from context.media_storage import store_blob
    from context.models import MediaAsset, PeerMedia
    from core import clock

    def run():
        upload = request.FILES.get("file")
        if upload is None:
            raise DomainError("file_required", "Choose a file to upload.")
        data = upload.read()
        ext = (upload.name.rsplit(".", 1)[-1] if "." in upload.name else "").lower()
        mismatch = reject_extension_mismatch(ext, data)
        if mismatch:
            raise DomainError("invalid_mime", "The file contents do not match an allowed image or video type.")
        if sniff_image_mime(data) is None:
            raise DomainError("invalid_mime", "Unsupported file contents.")
        try:
            digest, rel = store_blob(data, ext=ext or "bin")
        except ValueError as exc:
            raise DomainError(str(exc), "Storage quota blocked this upload.", status=409)
        post = PeerMedia.objects.get(pk=body.get("peer_media_id"))
        asset = MediaAsset.objects.create(
            post=post,
            role="analysis_image",
            content_hash=digest,
            relative_path=rel,
            mime_type=sniff_image_mime(data) or "",
            byte_size=len(data),
            captured_at=clock.now(),
            retention_class="owner_authorised_upload",
        )
        return {
            "asset_id": str(asset.pk),
            "note": "Upload is a separate authorised acquisition. It does not grant API metric permission.",
        }

    return idempotent(key, "media.upload", run)


@api
def media_clear_cache(request, body, key):
    from context.media_storage import evict_playback

    def run():
        if body.get("class") not in ("playback",):
            raise DomainError("invalid_cache_class", "Only the playback cache can be cleared here.")
        return evict_playback()

    return idempotent(key, "media.clear_cache", run)


@api
def media_job_status(request, body, key):
    from core.models import Job

    def run():
        job = Job.objects.get(pk=body["job_id"])
        return {"job_id": str(job.pk), "state": job.state, "task": job.task, "error": job.safe_error}

    return idempotent(key, "media.job_status", run)


@api
def media_review_features(request, body, key):
    from context.content_features import review_features

    def run():
        decisions = body.get("decisions") or []
        if isinstance(decisions, str) and decisions:
            decisions = json.loads(decisions)
        if not decisions and body.get("feature_key"):
            decisions = [
                {
                    "feature_key": body["feature_key"],
                    "review_state": body.get("review_state") or "accepted",
                    "value": body.get("value"),
                }
            ]
        review_features(
            body["peer_media_id"],
            decisions,
            expected_revision=int(body["expected_revision"]) if body.get("expected_revision") else None,
        )
        return {"ok": True}

    return idempotent(key, "media.review_features", run)


@api
def activity_detach_reference(request, body, key, activity_id):
    from context.inspiration_services import detach_reference

    def run():
        detach_reference(activity_id, body["reference_id"])
        return {"redirect": f"/ui/activity/{activity_id}"}

    return idempotent(key, f"activity.detach_ref.{activity_id}", run)


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
