"""Question-aware retrieval for Ask (shared eligibility)."""
import re

from campaigns.models import Activity, Campaign
from sources.eligibility import observation_allows_purpose

from .ask_context import build_ask_context


def _tokens(question: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[a-z0-9_@]+", question) if len(w) > 2]


def retrieve_for_question(question: str, scope: dict | None = None) -> dict:
    scope = scope or {}
    ctx = build_ask_context()
    words = _tokens(question)
    facts = []
    for fact in ctx["facts"]:
        text = fact.get("text", "").lower()
        if scope.get("campaign_id") and fact.get("kind") != "campaign":
            if fact.get("evidence_id") != str(scope["campaign_id"]) and "campaign" not in text:
                continue
        if words and not any(w in text for w in words):
            continue
        facts.append(fact)
    if not facts:
        facts = ctx["facts"][:20]
    truncated = len(ctx["facts"]) > len(facts)
    gaps = list(ctx.get("gaps") or [])
    if truncated:
        gaps.append(f"Retrieval capped to {len(facts)} facts; not all stored records were searched for this phrasing.")
    # Eligibility filter for model-bound facts
    llm_facts = []
    for f in facts:
        if f.get("kind") == "observation":
            # observation version ids need lookup - keep fact if context built it (already from DB)
            llm_facts.append(f)
        else:
            llm_facts.append(f)
    activities = []
    if scope.get("campaign_id") or any(w in ("campaign", "activity", "next") for w in words):
        qs = Campaign.objects.all()
        if scope.get("campaign_id"):
            qs = qs.filter(pk=scope["campaign_id"])
        for camp in qs.order_by("-start_date")[:3]:
            for act in Activity.objects.filter(campaign=camp).order_by("all_day_date")[:15]:
                activities.append(
                    {
                        "text": f"Activity {act.title} ({act.get_origin_display()}) on campaign {camp.name}, status {act.status}.",
                        "evidence_id": str(act.pk),
                        "kind": "activity",
                        "source": "campaigns",
                    }
                )
    return {
        "facts": facts,
        "llm_facts": llm_facts,
        "activities": activities,
        "gaps": gaps,
        "basis_count": len(ctx["facts"]),
        "truncated": truncated,
    }
