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
    inspiration = _inspiration_retrieval(question, scope)
    facts = facts + inspiration.get("facts", [])
    gaps = gaps + inspiration.get("gaps", [])
    return {
        "facts": facts,
        "llm_facts": llm_facts + inspiration.get("facts", []),
        "activities": activities,
        "gaps": gaps,
        "basis_count": len(ctx["facts"]) + len(inspiration.get("facts", [])),
        "truncated": truncated,
        "inspiration_run_id": inspiration.get("run_id"),
    }


def _inspiration_retrieval(question: str, scope: dict) -> dict:
    q = question.lower()
    if not any(w in q for w in ("example", "reference", "inspiration", "similar post", "peer post")):
        return {"facts": [], "gaps": []}
    from campaigns.models import Activity

    from intelligence.inspiration_service import recommend_for_activity

    activity = None
    ctx = {}
    if scope.get("activity_id"):
        activity = Activity.objects.filter(pk=scope["activity_id"]).first()
    if scope.get("campaign_id") and not activity:
        activity = Activity.objects.filter(campaign_id=scope["campaign_id"]).order_by("all_day_date").first()
    if activity:
        ctx = {
            "channel": activity.channel or "",
            "format": activity.format or "",
            "purpose": activity.purpose or "",
        }
    mode = "strong_public_response" if "strong" in q and "response" in q else "best_fit"
    out = recommend_for_activity(activity=activity, context=ctx, mode=mode, limit=5)
    facts = []
    for s in out.get("suggestions") or []:
        facts.append(
            {
                "text": (
                    f"Inspiration candidate ({s.get('tier', 'candidate')}): {s.get('peer_label', '')} "
                    f"{s.get('media_type_display', '')} — {s.get('match_reason', '')}"
                ),
                "evidence_id": str(s.get("id") or ""),
                "kind": "inspiration",
                "source": "intelligence.inspiration_service",
            }
        )
    gaps = list(out.get("gaps") or [])
    if not facts:
        gaps.append("No eligible inspiration examples matched this Ask phrasing and scope.")
    return {"facts": facts, "gaps": gaps, "run_id": out.get("run_id")}
