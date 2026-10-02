"""Per-metric evidence slices for tactic assessments (strict metric_id filter)."""
from datetime import timedelta

from core import clock
from findings.models import Finding
from sources.eligibility import finding_lineage_allows, observation_allows_purpose
from sources.models import Observation

from .tactics import tactic_observable_metrics


def build_metric_slice(ctx: dict, metric_id: str, purpose: str = "llm_ingest", max_obs: int = 8) -> dict:
    entity_ids = [e.pk for e in ctx.get("scope_entities") or []]
    refs = []
    finding_refs = []
    gaps = []
    cutoff = clock.now().date()
    start = ctx.get("start_date")
    window_start = start - timedelta(days=60) if start else cutoff - timedelta(days=60)
    window_end = ctx.get("end_date") or cutoff

    for finding in Finding.objects.filter(status="published", entity_id__in=entity_ids, metric_id=metric_id).order_by(
        "-computed_at"
    )[:4]:
        if not finding_lineage_allows(finding, purpose):
            continue
        bundle = finding.bundles.order_by("-version").first()
        if bundle:
            finding_refs.append(
                {
                    "finding_id": str(finding.pk),
                    "bundle_version": bundle.version,
                    "title": finding.title,
                    "metric_id": finding.metric_id,
                    "support": finding.lineage.get("support", "published"),
                }
            )
            for item in bundle.observation_refs[:max_obs]:
                if isinstance(item, dict) and item.get("metric_id") == metric_id:
                    refs.append(item)

    observations = (
        Observation.objects.filter(
            metric_id=metric_id,
            entity_id__in=entity_ids,
            period_start__gte=window_start,
            period_start__lte=window_end,
            active_version__isnull=False,
        )
        .select_related("metric", "active_version", "entity")
        .order_by("-period_start")[:max_obs]
    )
    for obs in observations:
        if not observation_allows_purpose(obs, purpose):
            gaps.append(f"Policy blocks {purpose} for {obs.metric_id} on {obs.period_start}.")
            continue
        val = obs.active_version.value
        snippet = f"{obs.entity.label}: {obs.metric.label} {obs.period_start} = {val}"
        refs.append(
            {
                "observation_version_id": str(obs.active_version_id) if obs.active_version_id else None,
                "observation_id": str(obs.pk),
                "metric_id": obs.metric_id,
                "entity_id": str(obs.entity_id),
                "period_start": str(obs.period_start),
                "snippet": snippet[:200],
            }
        )

    refs = refs[:max_obs]
    return {
        "metric_id": metric_id,
        "observation_refs": refs,
        "finding_refs": finding_refs,
        "gaps": gaps,
    }


def build_slices_for_tactics(ctx: dict, tactics: list, purpose: str = "llm_ingest") -> dict:
    metrics = set()
    for t in tactics:
        metrics.update(tactic_observable_metrics(t))
    return {mid: build_metric_slice(ctx, mid, purpose=purpose) for mid in sorted(metrics)}


def merge_slice_for_tactic(tactic: dict, slices: dict) -> dict:
    """Combine only observable metric slices for one tactic."""
    obs = []
    findings = []
    gaps = []
    for mid in tactic_observable_metrics(tactic):
        part = slices.get(mid) or {}
        obs.extend(part.get("observation_refs") or [])
        findings.extend(part.get("finding_refs") or [])
        gaps.extend(part.get("gaps") or [])
    return {"observation_refs": obs[:12], "finding_refs": findings[:6], "gaps": gaps}
