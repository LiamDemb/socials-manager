"""Derive strategic role priorities from campaign context (explicit rules, not LLM)."""
from datetime import date

NEEDS_RULES_VERSION = "needs-v1"

ROLE_ORDER_RELEASE = ["conversion", "engagement", "discovery", "measurement", "retention"]
ROLE_ORDER_GROWTH = ["discovery", "engagement", "conversion", "retention", "measurement"]
ROLE_ORDER_SHOW = ["engagement", "conversion", "discovery", "retention", "measurement"]


def _days_to_key(ctx) -> int | None:
    key = ctx.get("key_date")
    start = ctx.get("start_date")
    if not key or not start:
        return None
    if isinstance(key, date) and isinstance(start, date):
        return (key - start).days
    return None


def derive_campaign_needs(ctx: dict, bundle: dict | None = None, phase: str = "") -> dict:
    """Return ordered role priorities and disclosed data gaps."""
    bundle = bundle or {}
    group = ctx.get("campaign_group") or "growth"
    if group == "release":
        priorities = list(ROLE_ORDER_RELEASE)
        rationale = ["Release window: prioritise conversion to the promoted object, then sustaining engagement."]
    elif group == "show":
        priorities = list(ROLE_ORDER_SHOW)
        rationale = ["Show campaign: prioritise engagement and ticket/link conversion among selected channels."]
    else:
        priorities = list(ROLE_ORDER_GROWTH)
        rationale = ["Growth campaign: prioritise discovery and engagement; follower outcome is measured separately."]

    days_key = _days_to_key(ctx)
    if days_key is not None and days_key < 0:
        rationale.append("Pre-anchor phase: anticipation and reminder roles weighted alongside discovery.")
    elif phase in ("launch", "show_week"):
        rationale.append(f"Phase {phase}: time-sensitive conversion and engagement roles rise in priority.")

    data_gaps = []
    if not bundle.get("observation_refs") and not bundle.get("finding_refs"):
        data_gaps.append("No published findings or primary-outcome observations in the campaign evidence window.")
    if group == "growth" and ctx.get("primary_metric_id") == "instagram.account.followers.v1":
        has_ig = "instagram" in (ctx.get("channels") or [])
        if has_ig and not _has_metric_obs(bundle, "instagram.account.followers.v1"):
            data_gaps.append(
                "Follower conversion strength cannot be assessed without follower observations; discovery tactics may still be proposed as hypotheses."
            )

    return {
        "version": NEEDS_RULES_VERSION,
        "role_priorities": priorities,
        "needs_rationale": rationale,
        "data_gaps": data_gaps,
        "phase": phase,
    }


def _has_metric_obs(bundle: dict, metric_id: str) -> bool:
    for ref in bundle.get("observation_refs") or []:
        if ref.get("metric_id") == metric_id:
            return True
    return False
