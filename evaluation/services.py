"""Time-safe evaluation scaffolding. Gates are checked before any fitting or inference on observations."""
import hashlib
import json
from datetime import datetime, time, timedelta, timezone

from django.db import transaction
from django.db.models import Q

from core import clock
from core.errors import DomainError, PolicyDenied
from core.services import audit
from sources.models import ImportBatch, MetricDefinition, Observation, ObservationVersion, Source

from . import baselines
from .models import DatasetManifest, ForecastRecord, ModelRun

# Provisional engineering defaults, versioned. To be reviewed with data/impact rationale before any real holdout is opened.
READINESS_POLICY = {
    "version": "forecast-readiness-provisional-1",
    "min_active_days": 120,
    "min_development_origins": 4,
    "holdout_days": 28,
    "horizon_days": 7,
    "note": "Engineering defaults, not empirically selected thresholds. Active day = non-zero observed value.",
}


def utc_midnight(day):
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def as_of_series(entity, metric_id, cutoff, purpose):
    """Values known at `cutoff`: version available and contributed by an import committed (and not yet undone) by then.

    Only periods that closed by the cutoff are returned. Purpose policy is enforced per version.
    """
    for source in Source.objects.filter(observation__entity=entity, observation__metric_id=metric_id).distinct():
        policy = source.policies.order_by("-version").first()
        if policy is None or not policy.allows(purpose):
            raise PolicyDenied(purpose, f"{source.label} policy does not allow {purpose}.")
    obs_qs = Observation.objects.filter(entity=entity, metric_id=metric_id, period_end__lte=cutoff.date())
    versions = (
        ObservationVersion.objects.filter(observation__in=obs_qs, available_at__lte=cutoff)
        .filter(
            Q(contributions__batch__committed_at__lte=cutoff)
            & (Q(contributions__batch__undone_at__isnull=True) | Q(contributions__batch__undone_at__gt=cutoff))
        )
        .select_related("observation", "policy_version__source")
        .distinct()
    )
    best = {}
    for v in versions:
        key = v.observation_id
        if key not in best or v.version > best[key].version:
            best[key] = v
    out = []
    for v in best.values():
        if not v.policy_version.allows(purpose):
            raise PolicyDenied(purpose, f"{v.policy_version.source.label} policy v{v.policy_version.version} is {v.policy_version.purposes.get(purpose, 'unresolved')}.")
        if v.value is not None:
            out.append((v.observation.period_start, v.value, str(v.pk)))
    return sorted(out)


def _current_versions(entity, metric_id):
    return list(
        ObservationVersion.objects.filter(observation__entity=entity, observation__metric_id=metric_id, observation__active_version=models_f("pk"))
        .select_related("policy_version__source", "observation")
    )


def models_f(name):
    from django.db.models import F

    return F(name)


def gate_report(entity, metric_id, purpose="statistical_fit"):
    """Separate policy and history gates. Unknown policy denies. Never 'passed' by default."""
    versions = _current_versions(entity, metric_id)
    policies = {v.policy_version for v in versions}
    if not versions:
        policy_gate = {"status": "Insufficient data", "detail": "No stored observations."}
    else:
        denied = [p for p in policies if not p.allows(purpose)]
        policy_gate = (
            {"status": "Blocked", "detail": "; ".join(f"{p.source.label} policy v{p.version}: {purpose} is {p.purposes.get(purpose, 'unresolved')}" for p in denied)}
            if denied else {"status": "Passed", "detail": f"{purpose} allowed by {len(policies)} policy version(s)."}
        )
    active_days = sum(1 for v in versions if v.value)
    span = len(versions)
    need = READINESS_POLICY["min_active_days"]
    history_gate = (
        {"status": "Passed", "detail": f"{active_days} active days of {span} observed."}
        if active_days >= need else
        {"status": "Insufficient data", "detail": f"{active_days} active days of {span} observed; {need} required by {READINESS_POLICY['version']}. Zero-padded days before activity are not informative history."}
    )
    return {"policy": policy_gate, "history": history_gate, "readiness_policy": READINESS_POLICY["version"],
            "fit_allowed": policy_gate["status"] == "Passed" and history_gate["status"] == "Passed"}


def _fixture_class(versions):
    classes = {v.policy_version.source.fixture_class for v in versions}
    return classes.pop() if len(classes) == 1 else "mixed"


def plan_splits(days, horizon, holdout_days, min_origins):
    """Rolling development origins strictly before an untouched final holdout."""
    if not days:
        raise DomainError("insufficient_history", "No observations to split.")
    first, last = min(days), max(days)
    holdout_start = last - timedelta(days=holdout_days - 1)
    dev_last_origin = holdout_start - timedelta(days=horizon)
    origins = []
    origin = dev_last_origin
    while origin - timedelta(days=28) >= first and len(origins) < 12:
        origins.append(origin)
        origin -= timedelta(days=horizon)
    origins.reverse()
    if len(origins) < min_origins:
        raise DomainError("insufficient_history", f"Only {len(origins)} development origins fit before the holdout; {min_origins} required.")
    return {"horizon_days": horizon, "development_origins": [o.isoformat() for o in origins],
            "holdout": {"start": holdout_start.isoformat(), "end_exclusive": (last + timedelta(days=1)).isoformat()}}


@transaction.atomic
def freeze_manifest(entity, metric_id, cutoff, criteria, purpose="statistical_fit"):
    metric = MetricDefinition.objects.get(pk=metric_id)
    if metric.kind != "flow":
        raise DomainError("unsupported_target", "Evaluation currently supports daily flow trajectories only.")
    gates = gate_report(entity, metric_id, purpose)
    if gates["policy"]["status"] != "Passed":
        raise PolicyDenied(purpose, gates["policy"]["detail"])
    if gates["history"]["status"] != "Passed":
        raise DomainError("insufficient_history", gates["history"]["detail"])
    points = as_of_series(entity, metric_id, cutoff, purpose)
    if not criteria or "max_mae_ratio_vs_best_baseline" not in criteria:
        raise DomainError("criteria_required", "Predeclare acceptance criteria before freezing a dataset.")
    splits = plan_splits([d for d, _, _ in points], READINESS_POLICY["horizon_days"], READINESS_POLICY["holdout_days"], READINESS_POLICY["min_development_origins"])
    version_ids = [vid for _, _, vid in points]
    versions = list(ObservationVersion.objects.filter(pk__in=version_ids).select_related("policy_version__source"))
    content = json.dumps({"points": [(d.isoformat(), v) for d, v, _ in points], "splits": splits, "criteria": criteria}, sort_keys=True)
    manifest = DatasetManifest.objects.create(
        purpose=purpose, metric=metric, entity=entity, cutoff=cutoff, fixture_class=_fixture_class(versions),
        input_version_ids=version_ids, policy_version_ids=sorted({str(v.policy_version_id) for v in versions}),
        content_hash=hashlib.sha256(content.encode()).hexdigest(), splits=splits, criteria=criteria,
        readiness_policy=READINESS_POLICY["version"], gates=gates, frozen_at=clock.now(),
    )
    audit("dataset_manifest", manifest.pk, "freeze", {"hash": manifest.content_hash, "fixture_class": manifest.fixture_class})
    return manifest


def _frozen_points(manifest):
    versions = ObservationVersion.objects.filter(pk__in=manifest.input_version_ids).select_related("observation")
    return {v.observation.period_start: v.value for v in versions}


def evaluate_development(manifest, model_refs=("recent_mean_7", "seasonal_naive_7")):
    """Rolling-origin evaluation on development origins only. Features come from as-of history at each origin."""
    horizon = manifest.splits["horizon_days"]
    frozen = _frozen_points(manifest)
    results = {}
    for ref in model_refs:
        errors = []
        for origin_text in manifest.splits["development_origins"]:
            origin = datetime.fromisoformat(origin_text).date()
            cutoff = utc_midnight(origin)
            history = as_of_series(manifest.entity, manifest.metric_id, cutoff, manifest.purpose)
            if any(d >= origin for d, _, _ in history):
                raise DomainError("future_leak", "History contains a value at or after its origin.", status=500)
            prediction = baselines.predict(ref, [(d, v) for d, v, _ in history], horizon)
            target_days = [origin + timedelta(days=i) for i in range(horizon)]
            if not all(d in frozen for d in target_days):
                continue
            actual = sum(frozen[d] for d in target_days)
            errors.append({"origin": origin_text, "predicted": prediction, "actual": actual})
        results[ref] = baselines.score(errors)
    run = ModelRun.objects.create(
        purpose=manifest.purpose, model_ref=",".join(model_refs), manifest=manifest,
        configuration={"split": "development", "horizon_days": horizon}, report=results, state="development_evaluated", created_at=clock.now(),
    )
    return run


@transaction.atomic
def open_holdout(manifest, model_ref):
    updated = DatasetManifest.objects.filter(pk=manifest.pk, holdout_opened_at__isnull=True).update(holdout_opened_at=clock.now())
    if updated != 1:
        raise DomainError("holdout_used", "The final holdout has already been evaluated once.", status=409)
    manifest.refresh_from_db()
    horizon = manifest.splits["horizon_days"]
    frozen = _frozen_points(manifest)
    start = datetime.fromisoformat(manifest.splits["holdout"]["start"]).date()
    end = datetime.fromisoformat(manifest.splits["holdout"]["end_exclusive"]).date()
    errors = []
    origin = start
    while origin + timedelta(days=horizon) <= end:
        history = as_of_series(manifest.entity, manifest.metric_id, utc_midnight(origin), manifest.purpose)
        pred = baselines.predict(model_ref, [(d, v) for d, v, _ in history], horizon)
        days = [origin + timedelta(days=i) for i in range(horizon)]
        if all(d in frozen for d in days):
            errors.append({"origin": origin.isoformat(), "predicted": pred, "actual": sum(frozen[d] for d in days)})
        origin += timedelta(days=horizon)
    return ModelRun.objects.create(
        purpose=manifest.purpose, model_ref=model_ref, manifest=manifest, configuration={"split": "final_holdout"},
        report={model_ref: baselines.score(errors)}, state="holdout_evaluated", created_at=clock.now(),
    )


def record_prospective(entity, metric_id, model_ref, target_start, horizon_days=7, purpose="model_infer"):
    """Save a forecast before its outcome exists. Rejects windows whose outcome is already (partly) available."""
    now = clock.now()
    target_end = target_start + timedelta(days=horizon_days)
    if utc_midnight(target_start) <= now:
        raise DomainError("not_prospective", "A prospective forecast must be issued before its target window starts.")
    gates = gate_report(entity, metric_id, purpose)
    if gates["policy"]["status"] != "Passed":
        raise PolicyDenied(purpose, gates["policy"]["detail"])
    known = Observation.objects.filter(entity=entity, metric_id=metric_id, period_start__gte=target_start, period_start__lt=target_end,
                                       active_version__isnull=False)
    if known.exists():
        raise DomainError("outcome_known", "Some of this window is already observed.")
    history = as_of_series(entity, metric_id, now, purpose)
    if any(d >= target_start for d, _, _ in history):
        raise DomainError("future_leak", "History overlaps the target window.", status=500)
    prediction = baselines.predict(model_ref, [(d, v) for d, v, _ in history], horizon_days)
    versions = list(ObservationVersion.objects.filter(pk__in=[vid for _, _, vid in history]).select_related("policy_version__source"))
    record = ForecastRecord.objects.create(
        model_ref=model_ref, metric_id=metric_id, entity=entity, fixture_class=_fixture_class(versions) if versions else "none",
        issued_at=now, information_cutoff=now, target_start=target_start, target_end=target_end,
        prediction={"point": prediction, "interval": None, "note": "Baseline point forecast; no calibrated interval."},
        input_fingerprint=hashlib.sha256(json.dumps([(d.isoformat(), v) for d, v, _ in history]).encode()).hexdigest(),
    )
    audit("forecast", record.pk, "issue", {"model": model_ref, "target": [str(target_start), str(target_end)]})
    return record


def score_prospective(record):
    if record.state != "pending":
        return record
    values = {}
    for o in Observation.objects.filter(entity=record.entity, metric=record.metric, period_start__gte=record.target_start,
                                        period_start__lt=record.target_end, active_version__isnull=False).select_related("active_version"):
        values[o.period_start] = o.active_version.value
    days = (record.target_end - record.target_start).days
    if len(values) < days:
        return record
    actual = sum(values.values())
    record.actual = {"value": actual, "scored_at": clock.now().isoformat()}
    record.evaluation = {"absolute_error": abs(record.prediction["point"] - actual), "error": record.prediction["point"] - actual}
    record.state = "scored"
    record.save(update_fields=["actual", "evaluation", "state"])
    return record


def availability_ledger(limit=100):
    rows = []
    for b in ImportBatch.objects.filter(state__in=["committed", "undone"]).select_related("mapped_entity", "source").order_by("-committed_at")[:limit]:
        rows.append({
            "batch": b, "available_at": b.committed_at, "undone_at": b.undone_at,
            "first": b.summary.get("first_date"), "last": b.summary.get("last_date"),
            "export_generated_at": None,
        })
    return rows
