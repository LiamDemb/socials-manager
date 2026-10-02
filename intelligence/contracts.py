"""Campaign and metric contracts for intelligence (registry-aligned).

Planning relevance (tactic selection) is separate from evidence compatibility
(metric-scoped observations, findings, and outcome progress). Use metric_ids_match
only for the latter — never to hard-exclude tactics from a campaign plan.
"""
from campaigns import registry
from sources.models import MetricDefinition

ROLE_VOCABULARY = ("discovery", "engagement", "conversion", "retention", "measurement")


def campaign_group(campaign_type: str) -> str:
    spec = registry.TYPES.get(campaign_type) or {}
    return spec.get("group") or "growth"


def campaign_phase_type(campaign_type: str) -> str:
    """Scheduler phase input: growth, show, or release family."""
    group = campaign_group(campaign_type)
    if group == "show":
        return "show"
    if group == "growth":
        return "growth"
    return "release"


def metric_ids_match(candidate_ids: set[str], outcome_ids: set[str]) -> bool:
    """Evidence compatibility: may these metric IDs be discussed as the same proposition family."""
    if not outcome_ids:
        return True
    if candidate_ids.intersection(outcome_ids):
        return True
    codes = {mid.rsplit(".", 1)[0] for mid in outcome_ids if mid}
    for cid in candidate_ids:
        base = cid.rsplit(".", 1)[0]
        if base in codes or any(base.startswith(c.split(".")[0]) for c in codes):
            return True
    return False


def validate_tactic_catalogue(tactics: list) -> list[str]:
    errors = []
    known = set(MetricDefinition.objects.values_list("pk", flat=True))
    for t in tactics:
        if not t.get("roles"):
            errors.append(f"tactic {t['id']}: missing roles")
        metrics = set(t.get("observable_metrics") or t.get("outcome_metrics") or [])
        for mid in metrics:
            if mid not in known:
                errors.append(f"tactic {t['id']}: unknown metric {mid}")
    return errors
