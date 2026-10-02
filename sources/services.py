import csv
import hashlib
import io
import re
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Max

from catalogue.models import Entity, PromotedObject
from catalogue.services import create_object, own_artist
from core import clock
from core.errors import DomainError, PolicyDenied
from core.paths import durable_write, safe_path
from core.services import audit, emit, idempotent

from . import spotify_csv
from .metric_registry import S4A, column_metric_ids
from .models import (
    ImportBatch,
    MetricDefinition,
    Observation,
    ObservationContribution,
    ObservationVersion,
    RawFile,
    Source,
    SourcePolicyVersion,
    StagedIssue,
    StagedObservation,
)

SPOTIFY_ROUTE = "manual_csv"
SPOTIFY_POLICY_V1 = {
    "purposes": {
        "collect": "allowed",
        "store": "allowed",
        "display": "allowed",
        "descriptive_derive": "allowed",
        "export": "allowed",
        "statistical_fit": "unresolved",
        "model_infer": "unresolved",
        "llm_ingest": "unresolved",
    },
    "assessment_ref": (
        "Owner-directed import of the band's own Spotify for Artists CSV exports for internal display and descriptive "
        "aggregation (handoff D07, D08; spec/INTEGRATIONS.md). Numerical fitting, model inference and LLM ingestion are "
        "unresolved pending an applicable assessment (spec/DECISIONS.md gate); unknown denies."
    ),
    "conditions": "Private loopback installation. No public distribution, sale, audio ingestion or fan-level profiles.",
    "retention": {"raw_files": "retain until owner deletes the source", "derived": "inherits raw-file restrictions"},
}
SPOTIFY_CAPABILITY = {
    "route": "Manual CSV export from Spotify for Artists, reviewed import",
    "automatic_retrieval": {
        "state": "not_available",
        "reason": "No documented Spotify for Artists analytics API. The Web API Developer Policy restricts analytics use and the User Guidelines restrict automated collection.",
    },
    "metrics": {
        "Audience timeline": "supported: listeners, monthly/active/super listeners, artist streams, playlist adds, saves, followers (UTC days)",
        "Song streams timeline": "supported: daily streams for one recording (UTC days)",
        "Pre-saves": "not in these exports; needs a release-scoped provider report",
        "Local-day totals": "not available; Spotify days are UTC",
    },
}


def ensure_spotify_source():
    source, created = Source.objects.get_or_create(
        provider=S4A,
        route=SPOTIFY_ROUTE,
        defaults={"label": "Spotify for Artists", "capability": SPOTIFY_CAPABILITY, "state": "active"},
    )
    if not source.policies.exists():
        SourcePolicyVersion.objects.create(
            source=source,
            version=1,
            purposes=SPOTIFY_POLICY_V1["purposes"],
            assessment_ref=SPOTIFY_POLICY_V1["assessment_ref"],
            conditions=SPOTIFY_POLICY_V1["conditions"],
            retention=SPOTIFY_POLICY_V1["retention"],
            effective_at=clock.now(),
        )
    return source


def current_policy(source):
    policy = source.policies.order_by("-version").first()
    if policy is None:
        raise DomainError("no_policy", "This source has no use policy.")
    return policy


def require_purpose(policy, purpose):
    if not policy.allows(purpose):
        raise PolicyDenied(purpose, f"{policy.source.label} policy v{policy.version} marks it {policy.purposes.get(purpose, 'unresolved')}.")


def store_raw_file(raw: bytes, original_name: str) -> RawFile:
    digest = hashlib.sha256(raw).hexdigest()
    existing = RawFile.objects.filter(sha256=digest).first()
    if existing:
        return existing
    relative = f"imports/{digest[:2]}/{digest}.csv"
    target = safe_path(relative)
    if not target.exists():
        durable_write(target, raw)
    return RawFile.objects.create(
        sha256=digest, relative_path=relative, first_name=original_name[:255], size_bytes=len(raw), received_at=clock.now()
    )


def read_raw(raw_file: RawFile) -> bytes:
    data = safe_path(raw_file.relative_path).read_bytes()
    if hashlib.sha256(data).hexdigest() != raw_file.sha256:
        raise DomainError("raw_file_changed", "The stored original file no longer matches its hash.", status=500)
    return data


def suggested_label(filename):
    stem = re.sub(r"\.csv$", "", filename or "", flags=re.I)
    stem = re.sub(r"[-_ ]?timeline.*$", "", stem, flags=re.I)
    stem = re.sub(r"\s*\(\d+\)\s*$", "", stem)
    return stem.strip()[:120]


def preview_upload(raw: bytes, original_name: str):
    """Store exact bytes and stage parsed rows. Commits no observations."""
    if not raw:
        raise DomainError("empty_file", "The file is empty.", fields={"file": "Empty"})
    if len(raw) > settings.MAX_UPLOAD_BYTES:
        raise DomainError("file_too_large", f"Files up to {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB are supported.", fields={"file": "Too large"})
    name = re.sub(r"[\x00-\x1f/\\]", "_", original_name or "upload.csv")[:255]
    parsed = spotify_csv.parse(raw)
    source = ensure_spotify_source()
    policy = current_policy(source)
    require_purpose(policy, "collect")
    require_purpose(policy, "store")
    with transaction.atomic():
        raw_file = store_raw_file(raw, name)
        batch = ImportBatch.objects.create(
            source=source,
            policy_version=policy,
            raw_file=raw_file,
            original_name=name,
            scope=parsed.scope or "",
            parser_version=spotify_csv.PARSER_VERSION,
            state="invalid" if parsed.issues else "staged",
            created_at=clock.now(),
        )
        metrics = {m.pk: m for m in MetricDefinition.objects.filter(provider=S4A)}
        StagedObservation.objects.bulk_create(
            [StagedObservation(batch=batch, row_number=r, metric=metrics[m], period_start=d, value=v) for r, m, d, v in parsed.values],
            batch_size=2000,
        )
        StagedIssue.objects.bulk_create(
            [StagedIssue(batch=batch, row_number=r, column=c, code=code, message=msg) for r, c, code, msg in parsed.issues[:500]]
        )
        if parsed.scope == "artist" and not parsed.issues:
            artist = own_artist()
            if artist:
                _apply_mapping(batch, artist.entity)
        batch.summary = _summarise(batch, parsed.source_rows, len(parsed.issues))
        batch.save(update_fields=["summary"])
        audit("import_batch", batch.pk, "preview", {"file": name, "sha256": raw_file.sha256, "scope": batch.scope, "state": batch.state})
    return batch


def _existing_versions(source, entity, metric_ids, start, end):
    rows = Observation.objects.filter(
        source=source, entity=entity, metric_id__in=metric_ids, period_start__gte=start, period_start__lte=end, dimension_key=""
    ).select_related("active_version")
    return {(o.metric_id, o.period_start): o for o in rows}


def _classify(batch):
    """Compare staged rows with current active versions. Returns number of changed classifications."""
    staged = list(batch.staged.all())
    if not staged or batch.mapped_entity_id is None:
        return 0
    start = min(s.period_start for s in staged)
    end = max(s.period_start for s in staged)
    existing = _existing_versions(batch.source, batch.mapped_entity, {s.metric_id for s in staged}, start, end)
    changed = []
    for s in staged:
        obs = existing.get((s.metric_id, s.period_start))
        active = obs.active_version if obs else None
        if active is None:
            cls, ver = "new", None
        elif active.value == s.value:
            cls, ver = "equal", active
        else:
            cls, ver = "conflict", active
        if cls != s.classification or (ver.pk if ver else None) != s.existing_version_id:
            s.classification = cls
            s.existing_version = ver
            if cls != "conflict":
                s.approved = False
                s.approval_reason = ""
            changed.append(s)
    StagedObservation.objects.bulk_update(changed, ["classification", "existing_version", "approved", "approval_reason"], batch_size=2000)
    return len(changed)


def _summarise(batch, source_rows=None, issue_count=None):
    staged = batch.staged.all()
    counts = defaultdict(int)
    for cls in staged.values_list("classification", flat=True):
        counts[cls] += 1
    dates = staged.aggregate(first=models_min("period_start"), last=Max("period_start"))
    summary = dict(batch.summary or {})
    if source_rows is not None:
        summary["source_rows"] = source_rows
    if issue_count is not None:
        summary["issues"] = issue_count
    summary.update(
        {
            "metric_values": staged.count(),
            "new": counts["new"],
            "equal": counts["equal"],
            "conflict": counts["conflict"],
            "approved_conflicts": staged.filter(classification="conflict", approved=True).count(),
            "first_date": dates["first"].isoformat() if dates["first"] else None,
            "last_date": dates["last"].isoformat() if dates["last"] else None,
            "mapped": batch.mapped_entity_id is not None,
        }
    )
    return summary


def models_min(field):
    from django.db.models import Min

    return Min(field)


def _apply_mapping(batch, entity):
    if batch.scope == "artist":
        artist = own_artist()
        if not artist or entity.pk != artist.pk:
            raise DomainError("scope_mismatch", "An Audience timeline belongs to this installation's own artist.")
    elif batch.scope == "recording":
        obj = PromotedObject.objects.filter(pk=entity.pk, kind="recording").first()
        if obj is None:
            raise DomainError("scope_mismatch", "A song streams timeline must map to a recording, not an artist, release or event.")
    else:
        raise DomainError("unmappable", "This file has no supported scope.")
    batch.mapped_entity = entity
    batch.save(update_fields=["mapped_entity"])
    _classify(batch)


def batch_for_update(batch_id, expected_preview_revision):
    batch = ImportBatch.objects.select_related("source", "mapped_entity", "raw_file", "policy_version").get(pk=batch_id)
    if batch.state != "staged":
        raise DomainError("batch_not_staged", f"This import is {batch.state}; start a new preview.", status=409)
    if batch.preview_revision != expected_preview_revision:
        raise DomainError("stale_preview", "The preview changed. Review the current preview before continuing.", status=409)
    return batch


def _bump(batch):
    updated = ImportBatch.objects.filter(pk=batch.pk, preview_revision=batch.preview_revision, state="staged").update(
        preview_revision=batch.preview_revision + 1
    )
    if updated != 1:
        raise DomainError("stale_preview", "The preview changed. Review the current preview before continuing.", status=409)
    batch.preview_revision += 1


@transaction.atomic
def set_mapping(batch_id, expected_preview_revision, entity_id=None, new_recording_label=None):
    batch = batch_for_update(batch_id, expected_preview_revision)
    if new_recording_label:
        if batch.scope != "recording":
            raise DomainError("scope_mismatch", "Only a song streams timeline creates a recording.")
        entity = create_object("recording", new_recording_label).entity
    elif entity_id:
        entity = Entity.objects.get(pk=entity_id)
    else:
        raise DomainError("mapping_required", "Choose what this file measures.", fields={"entity": "Required"})
    _apply_mapping(batch, entity)
    _bump(batch)
    batch.summary = _summarise(batch)
    batch.save(update_fields=["summary"])
    audit("import_batch", batch.pk, "map", {"entity": str(entity.pk), "label": entity.label}, revision=batch.preview_revision)
    return batch


@transaction.atomic
def refresh_preview(batch_id):
    """Re-check a staged preview against current stored data; bumps the revision if anything changed."""
    batch = ImportBatch.objects.select_related("source", "mapped_entity").get(pk=batch_id)
    if batch.state != "staged" or batch.mapped_entity_id is None:
        return batch
    if _classify(batch):
        _bump(batch)
        batch.summary = _summarise(batch)
        batch.save(update_fields=["summary"])
    return batch


@transaction.atomic
def approve_conflicts(batch_id, expected_preview_revision, staged_ids, reason):
    batch = batch_for_update(batch_id, expected_preview_revision)
    reason = (reason or "").strip()
    if not reason:
        raise DomainError("reason_required", "Say why the revised values are correct.", fields={"reason": "Required"})
    qs = batch.staged.filter(classification="conflict")
    if staged_ids != "all":
        qs = qs.filter(pk__in=staged_ids)
    count = qs.update(approved=True, approval_reason=reason[:500])
    _bump(batch)
    batch.summary = _summarise(batch)
    batch.save(update_fields=["summary"])
    audit("import_batch", batch.pk, "approve_revisions", {"count": count, "reason": reason[:500]}, revision=batch.preview_revision)
    return batch


def commit(batch_id, expected_preview_revision, idempotency_key):
    return idempotent(idempotency_key, f"import.commit:{batch_id}", lambda: _commit(batch_id, expected_preview_revision))


def _commit(batch_id, expected_preview_revision):
    batch = batch_for_update(batch_id, expected_preview_revision)
    if batch.mapped_entity_id is None:
        raise DomainError("mapping_required", "Choose what this file measures before importing.")
    if batch.issues.exists():
        raise DomainError("invalid_rows", "Fix the invalid rows and upload again.")
    policy = current_policy(batch.source)
    if policy.pk != batch.policy_version_id:
        raise DomainError("stale_policy", "The source use policy changed since this preview. Start a new preview.", status=409)
    require_purpose(policy, "store")
    read_raw(batch.raw_file)
    if _classify(batch):
        # Rolled back with this transaction; refresh_preview() persists the new classification on view.
        raise DomainError("stale_preview", "Stored data changed since this preview. Review the updated preview.", status=409)
    staged = list(batch.staged.select_related("existing_version", "metric").all())
    unapproved = [s for s in staged if s.classification == "conflict" and not s.approved]
    if unapproved:
        raise DomainError(
            "unapproved_revisions",
            f"{len(unapproved)} values differ from stored data. Approve the revisions with a reason, or cancel this import.",
            status=409,
        )
    now = clock.now()
    row_ref = lambda s: f"{batch.raw_file.sha256[:12]}:row{s.row_number}:{s.metric.csv_column}"  # noqa: E731
    new_obs, new_versions, contributions = [], [], []
    for s in staged:
        if s.classification == "new":
            obs = Observation(
                source=batch.source, entity_id=batch.mapped_entity_id, metric_id=s.metric_id,
                period_start=s.period_start, period_end=s.period_start + timedelta(days=1),
            )
            ver = ObservationVersion(
                observation=obs, version=1, value=s.value, available_at=now, policy_version=policy, source_row_ref=row_ref(s)
            )
            new_obs.append(obs)
            new_versions.append(ver)
            contributions.append(ObservationContribution(version=ver, batch=batch, row_ref=row_ref(s)))
        elif s.classification == "equal":
            contributions.append(ObservationContribution(version=s.existing_version, batch=batch, row_ref=row_ref(s)))
        else:
            prior = s.existing_version
            top = ObservationVersion.objects.filter(observation_id=prior.observation_id).aggregate(m=Max("version"))["m"]
            ver = ObservationVersion(
                observation_id=prior.observation_id, version=top + 1, value=s.value, available_at=now, policy_version=policy,
                source_row_ref=row_ref(s), supersedes=prior, revision_reason=s.approval_reason,
            )
            new_versions.append(ver)
            contributions.append(ObservationContribution(version=ver, batch=batch, row_ref=row_ref(s)))
    Observation.objects.bulk_create(new_obs, batch_size=2000)
    for v in new_versions:
        if v.observation_id is None:
            v.observation_id = v.observation.pk
    ObservationVersion.objects.bulk_create(new_versions, batch_size=2000)
    ObservationContribution.objects.bulk_create(contributions, batch_size=2000, ignore_conflicts=True)
    affected = {v.observation_id for v in new_versions}
    _recompute_active(affected)
    updated = ImportBatch.objects.filter(pk=batch.pk, state="staged", preview_revision=expected_preview_revision).update(
        state="committed", committed_at=now
    )
    if updated != 1:
        raise DomainError("batch_not_staged", "This import was already committed.", status=409)
    batch.refresh_from_db()
    summary = _summarise(batch)
    summary["committed"] = {"new_facts": len(new_obs), "revisions": sum(1 for s in staged if s.classification == "conflict"),
                            "unchanged": sum(1 for s in staged if s.classification == "equal")}
    batch.summary = summary
    batch.save(update_fields=["summary"])
    emit("observations.changed", {"batch": str(batch.pk), "action": "commit", "entity": str(batch.mapped_entity_id), "at": now.isoformat()})
    audit("import_batch", batch.pk, "commit", summary["committed"])
    return {"batch_id": str(batch.pk), "state": "committed", **summary["committed"]}


def _recompute_active(observation_ids):
    """Active version = highest version with at least one active contribution."""
    for obs_id in observation_ids:
        top = (
            ObservationVersion.objects.filter(observation_id=obs_id, contributions__active=True)
            .order_by("-version")
            .values_list("pk", flat=True)
            .first()
        )
        Observation.objects.filter(pk=obs_id).update(active_version_id=top)


def undo(batch_id, reason, idempotency_key):
    return idempotent(idempotency_key, f"import.undo:{batch_id}", lambda: _undo(batch_id, reason))


def _undo(batch_id, reason):
    reason = (reason or "").strip()
    if not reason:
        raise DomainError("reason_required", "Say why you are undoing this import.", fields={"reason": "Required"})
    now = clock.now()
    updated = ImportBatch.objects.filter(pk=batch_id, state="committed").update(state="undone", undone_at=now, undo_reason=reason[:500])
    if updated != 1:
        raise DomainError("not_committed", "Only a committed import can be undone.", status=409)
    batch = ImportBatch.objects.get(pk=batch_id)
    affected = set(ObservationContribution.objects.filter(batch=batch, active=True).values_list("version__observation_id", flat=True))
    ObservationContribution.objects.filter(batch=batch).update(active=False)
    _recompute_active(affected)
    retained = Observation.objects.filter(pk__in=affected, active_version__isnull=False).count()
    emit("observations.changed", {"batch": str(batch.pk), "action": "undo", "entity": str(batch.mapped_entity_id), "at": now.isoformat()})
    audit("import_batch", batch.pk, "undo", {"reason": reason[:500], "affected": len(affected), "still_supported": retained})
    return {"batch_id": str(batch.pk), "state": "undone", "affected": len(affected), "still_supported": retained}


@transaction.atomic
def cancel_preview(batch_id):
    updated = ImportBatch.objects.filter(pk=batch_id, state__in=["staged", "invalid"]).update(state="rejected")
    if updated != 1:
        raise DomainError("not_staged", "Only a preview can be cancelled.", status=409)
    audit("import_batch", batch_id, "cancel")


# Reads


def active_observations(entity=None, metric=None, purpose="display"):
    qs = Observation.objects.filter(active_version__isnull=False).select_related("active_version__policy_version", "metric", "entity")
    if entity is not None:
        qs = qs.filter(entity=entity)
    if metric is not None:
        qs = qs.filter(metric=metric)
    return qs


def series(entity, metric_id, purpose="display", start=None, end=None):
    """Active daily values for one entity/metric, enforcing source purpose. end is exclusive."""
    qs = active_observations(entity=entity).filter(metric_id=metric_id)
    if start:
        qs = qs.filter(period_start__gte=start)
    if end:
        qs = qs.filter(period_start__lt=end)
    out = []
    for o in qs.order_by("period_start"):
        require_purpose(o.active_version.policy_version, purpose)
        out.append((o.period_start, o.active_version.value, o.active_version_id))
    return out


def data_through(entity, metric_id):
    return active_observations(entity=entity).filter(metric_id=metric_id).aggregate(m=Max("period_start"))["m"]


def committed_entities():
    ids = Observation.objects.filter(active_version__isnull=False).values_list("entity_id", flat=True).distinct()
    return list(Entity.objects.filter(pk__in=ids).order_by("kind", "label"))


SPREADSHEET_PREFIX = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(SPREADSHEET_PREFIX) else text


def export_source_shaped(entity, purpose="export"):
    obs = list(active_observations(entity=entity).filter(metric__provider=S4A))
    if not obs:
        raise DomainError("no_data", "No stored Spotify data for this item.", status=404)
    for o in obs:
        require_purpose(o.active_version.policy_version, purpose)
    scope = "artist" if entity.kind == "artist" else "recording"
    columns = dict((m, c) for c, m in column_metric_ids(scope))
    rows = defaultdict(dict)
    for o in obs:
        if o.metric_id in columns:
            rows[o.period_start][columns[o.metric_id]] = o.active_version.value
    return spotify_csv.source_shaped_csv(scope, rows)


def export_common(entity=None, purpose="export"):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["provider", "entity_scope", "entity_id", "entity_label", "metric_id", "metric_label", "period_start_utc",
                     "period_end_utc", "value", "version", "available_at_utc", "source_row_ref", "contributing_imports"])
    qs = active_observations(entity=entity).order_by("entity__label", "metric_id", "period_start").prefetch_related("active_version__contributions")
    for o in qs:
        v = o.active_version
        require_purpose(v.policy_version, purpose)
        batches = ";".join(sorted(str(c.batch_id) for c in v.contributions.all() if c.active))
        writer.writerow([_safe_cell(x) for x in [o.metric.provider, o.metric.scope_kind, o.entity_id, o.entity.label, o.metric_id, o.metric.label,
                         o.period_start.isoformat(), o.period_end.isoformat(), v.value, v.version, v.available_at.isoformat(), v.source_row_ref, batches]])
    return out.getvalue().encode()
