"""Deterministic reference suggestions for activities (no invented posts)."""
from context.library import explore_media_queryset, media_card, reference_card
from context.models import InspirationReference


def _format_channel(channel: str) -> str:
    return (channel or "").strip().lower()


def rank_explore_for_activity(channel="", fmt="", campaign_type="", strategic_role="", limit=3):
    qs = explore_media_queryset()
    scored = []
    for media in qs[:120]:
        card = media_card(media, is_saved=media.is_saved if hasattr(media, "is_saved") else False)
        score = 0
        reasons = []
        if channel and card["channel"] == _format_channel(channel):
            score += 3
            reasons.append(card["channel"])
        mt = (fmt or "").lower()
        if mt and mt in (card["media_type"] or "").lower():
            score += 2
            reasons.append(card["media_type_display"])
        if card["peer_role"] == "comparable":
            score += 1
        if strategic_role and strategic_role in ("story", "teaser", "announce"):
            if "video" in (card["media_type"] or "").lower() or "reel" in (card["media_type"] or "").lower():
                score += 1
                reasons.append("format fit")
        if score <= 0 and not channel:
            score = 1
            reasons.append("recent peer example")
        if score > 0:
            label = " · ".join(filter(None, reasons)) or "reference peer"
            card["match_reason"] = f"{card['media_type_display']} · {label}"
            card["match_score"] = score
            scored.append(card)
    scored.sort(key=lambda c: (-c["match_score"], c.get("published_at") or ""), reverse=False)
    scored.sort(key=lambda c: -c["match_score"])
    return scored[:limit]


def suggest_for_preview_activity(activity_fields: dict, limit=2):
    return rank_explore_for_activity(
        channel=activity_fields.get("channel") or "",
        fmt=activity_fields.get("format") or "",
        campaign_type=activity_fields.get("campaign_type") or "",
        strategic_role=(activity_fields.get("provenance") or {}).get("role") or "",
        limit=limit,
    )


def attached_cards_for_activity(activity):
    links = activity.reference_links.select_related("reference", "reference__peer_media", "reference__peer_media__peer")
    out = []
    for link in links:
        out.append(
            {
                **reference_card(link.reference),
                "attachment_origin": link.origin,
                "attachment_note": link.note,
            }
        )
    return out
