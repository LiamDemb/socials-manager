"""Purpose-aware source eligibility from contributing lineage."""
from sources.models import MetricDefinition, Observation, Source
from sources.services import current_policy


def source_for_provider(provider: str) -> Source | None:
    return Source.objects.filter(provider=provider, state="active").order_by("revision").first()


def policy_allows_provider(provider: str, purpose: str) -> bool:
    source = source_for_provider(provider)
    if not source:
        return False
    try:
        return current_policy(source).allows(purpose)
    except Exception:
        return False


def metric_allows_purpose(metric_id: str, purpose: str) -> bool:
    metric = MetricDefinition.objects.filter(pk=metric_id).first()
    if not metric:
        return False
    return policy_allows_provider(metric.provider, purpose)


def observation_allows_purpose(obs: Observation, purpose: str) -> bool:
    return metric_allows_purpose(obs.metric_id, purpose)


def finding_lineage_allows(finding, purpose: str) -> bool:
    """Derived findings inherit restrictions recorded in lineage."""
    blocked = (finding.lineage or {}).get("blocked_purposes") or []
    if purpose in blocked:
        return False
    provider = (finding.lineage or {}).get("provider")
    if provider:
        return policy_allows_provider(provider, purpose)
    if finding.metric_id:
        return metric_allows_purpose(finding.metric_id, purpose)
    return True
