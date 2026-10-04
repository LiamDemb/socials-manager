"""Recommend references for activities (M06/M09)."""
from core import clock

from context.models import InspirationRecommendationRun, RecommendationExposure

from .inspiration_request import build_inspiration_request
from .inspiration_retrieve import retrieve_candidates
from .inspiration_rank import rank_candidates


def recommend_for_activity(activity=None, context: dict | None = None, mode="best_fit", limit=3):
    rec, payload = build_inspiration_request(activity=activity, context=context or {}, mode=mode)
    retrieval = retrieve_candidates(payload)
    ranked = rank_candidates(payload, retrieval, mode=mode)
    run = InspirationRecommendationRun.objects.create(
        request=rec,
        policy_version=ranked["policy_version"],
        request_fingerprint=rec.fingerprint,
        candidates=ranked["candidates"][:limit],
        excluded=ranked["excluded"],
        gaps=retrieval.get("gaps") or [],
        created_at=clock.now(),
    )
    suggestions = []
    for position, c in enumerate(ranked["candidates"][:limit], start=1):
        line = c["reasons"][0]["text"] if c.get("reasons") else "Reference example"
        suggestions.append(
            {
                **c,
                "match_reason": line,
                "recommendation_run_id": str(run.pk),
            }
        )
        if c.get("id"):
            RecommendationExposure.objects.create(
                run=run,
                peer_media_id=c["id"],
                event="shown",
                position=position,
                created_at=clock.now(),
            )
    return {
        "run_id": str(run.pk),
        "suggestions": suggestions,
        "gaps": (retrieval.get("gaps") or []) + (ranked.get("gaps") or []),
    }


def recommend_for_preview_fields(fields: dict, limit=2):
    return recommend_for_activity(activity=None, context=fields, limit=limit)
