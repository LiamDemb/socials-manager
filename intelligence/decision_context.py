"""Frozen decision context for planner, Ask, and approval."""
DECISION_CONTEXT_VERSION = "decision-context-v1"


def freeze_context(campaign_payload: dict, ctx: dict, bundle: dict, needs: dict, agenda_results: list) -> dict:
    import hashlib
    import json

    from .cohorts import build_comparable_cohort
    from .lineage import cache_key

    cohort = build_comparable_cohort()
    body = {
        "version": DECISION_CONTEXT_VERSION,
        "campaign_type": ctx.get("campaign_type"),
        "primary_metric_id": ctx.get("primary_metric_id"),
        "needs": needs,
        "bundle_fingerprint": bundle.get("fingerprint"),
        "cohort": cohort,
        "agenda_results": agenda_results,
        "policy_versions": bundle.get("policy_versions") or {},
    }
    fp = cache_key(body)
    timing = None
    for ar in agenda_results:
        if ar.get("request", {}).get("requested_use") == "scheduling":
            res = ar.get("result") or {}
            timing = (res.get("timing_evidence") or res.get("result", {}).get("timing_evidence"))
            break
    return {**body, "fingerprint": fp, "timing_evidence": timing}
