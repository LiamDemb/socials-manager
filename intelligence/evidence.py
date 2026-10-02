"""Build frozen evidence bundles from findings and observations under source policy."""
import hashlib
import json
from datetime import timedelta

from core import clock
from findings.models import EvidenceBundle, Finding
from sources.eligibility import finding_lineage_allows, observation_allows_purpose
from sources.models import Observation
from sources.eligibility import source_for_provider
from sources.services import current_policy

from .planning import resolve_planning_context


def _obs_ref(obs: Observation, snippet: str = "") -> dict:
    av = obs.active_version_id
    return {
        "observation_version_id": str(av) if av else None,
        "observation_id": str(obs.pk),
        "metric_id": obs.metric_id,
        "entity_id": str(obs.entity_id),
        "period_start": str(obs.period_start),
        "snippet": snippet[:200],
    }


def build_bundle_for_campaign(payload: dict, purpose: str = "llm_ingest", max_obs: int = 12) -> dict:
    """Return bundle dict with observation/finding refs for synthesis."""
    ctx = resolve_planning_context(payload)
    entity_ids = [e.pk for e in ctx["scope_entities"]]
    metric_ids = [ctx["primary_metric_id"]] if ctx["primary_metric_id"] else []
    refs = []
    finding_refs = []
    gaps = []
    cutoff = clock.now().date()
    window_start = ctx["start_date"] - timedelta(days=60) if ctx["start_date"] else cutoff - timedelta(days=60)
    window_end = ctx["end_date"] or cutoff

    for finding in Finding.objects.filter(status="published", entity_id__in=entity_ids).order_by("-computed_at")[:8]:
        if not finding_lineage_allows(finding, purpose):
            gaps.append(f"Finding {finding.title[:40]} excluded by source policy for {purpose}.")
            continue
        bundle = finding.bundles.order_by("-version").first()
        if bundle:
            finding_refs.append(
                {
                    "finding_id": str(finding.pk),
                    "bundle_version": bundle.version,
                    "title": finding.title,
                    "support": finding.lineage.get("support", "published"),
                }
            )
            for item in bundle.observation_refs[:max_obs]:
                if isinstance(item, dict) and item.get("observation_version_id"):
                    refs.append(item)

    if len(refs) < max_obs:
        for metric_id in metric_ids:
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
                refs.append(_obs_ref(obs, snippet))

    refs = refs[:max_obs]
    policy_versions = {}
    for provider in {ctx["primary_metric"].provider if ctx["primary_metric"] else ""}:
        if provider:
            src = source_for_provider(provider)
            if src:
                try:
                    policy_versions[provider] = current_policy(src).version
                except Exception:
                    pass

    fingerprint = hashlib.sha256(
        json.dumps({"refs": refs, "findings": finding_refs, "cutoff": str(cutoff)}, sort_keys=True).encode()
    ).hexdigest()[:32]

    if not refs and not finding_refs:
        gaps.append("No eligible observations or published findings in scope for this campaign window.")

    return {
        "id": f"bundle-{fingerprint[:12]}",
        "fingerprint": fingerprint,
        "observation_refs": refs,
        "finding_refs": finding_refs,
        "gaps": gaps,
        "frozen_at": clock.now().isoformat(),
        "campaign_type": ctx["campaign_type"],
        "entity_ids": [str(i) for i in entity_ids],
        "metric_ids": metric_ids,
        "window_start": str(window_start),
        "window_end": str(window_end),
        "policy_versions": policy_versions,
        "purpose": purpose,
    }


# Backward-compatible alias
def build_bundle(campaign_type, metric_ids, max_obs=12):
    payload = {"type": campaign_type, "primary_outcome": {"metric_id": metric_ids[0] if metric_ids else ""}}
    return build_bundle_for_campaign(payload, max_obs=max_obs)
