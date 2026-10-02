"""Cache keys and invalidation across policy, cohort, dataset and implementation versions."""
import hashlib
import json

LINEAGE_VERSION = "lineage-v1"


def cache_key(parts: dict) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def lineage_parts(
    spec_key: str,
    metric_id: str,
    cohort_fingerprint: str,
    dataset_hash: str,
    policy_versions: dict,
    feature_version: str | None = None,
    impl_version: str = "stats-v1",
) -> dict:
    from .registry import REGISTRY_VERSION

    feature_version = feature_version or REGISTRY_VERSION
    return {
        "lineage": LINEAGE_VERSION,
        "spec_key": spec_key,
        "metric_id": metric_id,
        "cohort_fingerprint": cohort_fingerprint,
        "dataset_hash": dataset_hash,
        "policy_versions": policy_versions,
        "feature_version": feature_version,
        "impl_version": impl_version,
    }


def mark_fits_stale(reason: str, cohort_fingerprint: str | None = None):
    from .models import FitRun

    qs = FitRun.objects.filter(status__in=("ready", "qualified", "exploratory", "descriptive_only"))
    if cohort_fingerprint:
        qs = qs.filter(lineage__cohort_fingerprint=cohort_fingerprint)
    for run in qs:
        run.status = "stale"
        run.lineage = {**(run.lineage or {}), "stale_reason": reason}
        run.save(update_fields=["status", "lineage"])


def flag_draft_activities_stale(campaign_id=None):
    from campaigns.models import Activity

    qs = Activity.objects.filter(origin="evidence_recommendation")
    if campaign_id:
        qs = qs.filter(campaign_id=campaign_id)
    for act in qs:
        detail = act.origin_detail or {}
        if detail.get("stale_rationale"):
            continue
        act.origin_detail = {**detail, "stale_rationale": True, "stale_reason": "upstream_evidence_or_policy_changed"}
        act.save(update_fields=["origin_detail"])
