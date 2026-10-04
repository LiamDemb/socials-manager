"""inspiration-rank-v1 deterministic ranker (section 10)."""
from intelligence.response_support import performance_adjustment
from intelligence.transfer_registry import find_bridge

POLICY_VERSION = "inspiration-rank-v1"
RRF_K = 60
WEIGHTS = {"structured": 1.0, "text": 1.0, "visual": 0.75}
MMR_LAMBDA = 0.85
MAX_SUGGESTIONS = 5
MAX_PER_ARTIST = 2
ROUTE_KEYS = ("structured", "fts", "visual")
WEIGHT_KEY = {"structured": "structured", "fts": "text", "visual": "visual"}


def _reviewed_purpose(card: dict) -> str:
    return str(card.get("reviewed_purpose") or "").lower()


def _tier(request: dict, card: dict) -> int:
    purpose = (request.get("purpose") or "").lower()
    fmt = (request.get("format") or "").lower()
    reviewed = _reviewed_purpose(card)
    media_type = (card.get("media_type") or "").lower()
    fmt_match = bool(fmt) and fmt in media_type
    bridge = find_bridge(media_type, fmt) if fmt and not fmt_match else None
    contradiction = bool(card.get("feasibility_contradiction"))
    purpose_match = bool(purpose) and reviewed == purpose
    if purpose_match and fmt_match and not contradiction:
        return 1
    if (purpose_match or card.get("style_match")) and bridge and not contradiction:
        card["transfer_bridge"] = bridge
        return 2
    caption = (card.get("caption_excerpt") or "").lower()
    suggested = bool(card.get("routes")) or (purpose and purpose in caption)
    if suggested:
        return 3
    return 0


def reciprocal_rank_fusion(card: dict, available_routes: list[str] | None = None, weights: dict | None = None) -> float:
    """F(c) = sum(w/(60+rank)) / sum(w/61) over routes available for the request."""
    weights = weights or WEIGHTS
    routes = available_routes or [r for r in ROUTE_KEYS if (card.get("routes") or {}).get(r)]
    if not routes:
        return 0.0
    numerator = 0.0
    denominator = 0.0
    present = card.get("routes") or {}
    for route in routes:
        w = weights[WEIGHT_KEY[route]]
        denominator += w / (RRF_K + 1)
        rank = present.get(route)
        if rank:
            numerator += w / (RRF_K + rank)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _similarity(a: dict, b: dict) -> float:
    if a.get("id") and a.get("id") == b.get("id"):
        return 1.0
    if a.get("near_duplicate_group") and a.get("near_duplicate_group") == b.get("near_duplicate_group"):
        return 1.0
    va = a.get("embedding")
    vb = b.get("embedding")
    if not va or not vb or len(va) != len(vb):
        return 0.0
    dot = sum(x * y for x, y in zip(va, vb))
    return max(0.0, min(1.0, dot))


def mmr_select(ranked: list[dict], limit: int) -> tuple[list[dict], bool]:
    remaining = sorted(ranked, key=lambda x: (-x["utility"], str(x.get("canonical_key") or x.get("id"))))
    selected = []
    per_artist = {}
    relaxed = False
    while remaining and len(selected) < limit:
        best = None
        best_key = None
        for item in remaining:
            artist = item.get("peer_label") or ""
            if per_artist.get(artist, 0) >= MAX_PER_ARTIST and not relaxed:
                continue
            redundancy = max((_similarity(item, s) for s in selected), default=0.0)
            score = MMR_LAMBDA * item["utility"] - (1 - MMR_LAMBDA) * redundancy
            key = (score, -ord(str(item.get("id") or "z")[:1]), str(item.get("id")))
            if best is None or key > best_key:
                best = item
                best_key = key
        if best is None:
            if not relaxed:
                relaxed = True
                continue
            break
        if best_key[0] <= 0 and selected:
            remaining.remove(best)
            continue
        selected.append(best)
        remaining.remove(best)
        artist = best.get("peer_label") or ""
        per_artist[artist] = per_artist.get(artist, 0) + 1
    return selected, relaxed


def rank_candidates(request: dict, retrieval: dict, mode: str = "best_fit") -> dict:
    weights = dict(WEIGHTS)
    if mode == "similar_look":
        weights["visual"] = 1.5
    available = []
    counts = retrieval.get("route_counts") or {}
    for route in ROUTE_KEYS:
        if counts.get(route):
            available.append(route)
    if not available:
        available = ["structured", "fts"]
    candidates = []
    excluded = []
    for card in retrieval.get("candidates") or []:
        tier = _tier(request, card)
        if tier == 0:
            excluded.append({"id": card.get("id"), "reason": "no_relevance_signal"})
            continue
        fusion = reciprocal_rank_fusion(card, available_routes=available, weights=weights)
        adjustment, reason, pathway = performance_adjustment(card, mode=mode)
        utility = max(0.0, min(1.0, fusion + adjustment))
        reasons = [{"kind": "creative_match", "text": _creative_line(card, tier)}]
        if adjustment != 0:
            reasons.append({"kind": "observed_response", "text": reason})
        elif reason:
            reasons.append({"kind": "limitation", "text": reason})
        if card.get("transfer_bridge"):
            reasons.append({"kind": "transfer_assumption", "text": card["transfer_bridge"]["limitation"]})
            reasons.append(
                {
                    "kind": "creative_adaptation",
                    "text": f"Transferable element: {card['transfer_bridge'].get('element', 'registered bridge')}.",
                }
            )
        candidates.append(
            {
                **card,
                "tier": tier,
                "fusion": fusion,
                "adjustment": adjustment,
                "adjustment_pathway": pathway,
                "utility": utility,
                "reasons": reasons,
            }
        )
    candidates.sort(key=lambda c: (c["tier"], -c["utility"], str(c.get("id"))))
    chosen, relaxed = mmr_select(candidates, MAX_SUGGESTIONS)
    gaps = []
    if relaxed:
        gaps.append("artist_cap_relaxed: fewer than five relevant examples without repeating artists.")
    return {
        "policy_version": POLICY_VERSION,
        "candidates": chosen,
        "excluded": excluded,
        "weights": weights,
        "gaps": gaps,
        "artist_cap_relaxed": relaxed,
    }


def _creative_line(card: dict, tier: int) -> str:
    label = card.get("media_type_display") or "Post"
    peer = card.get("peer_label") or "peer"
    if tier == 1:
        return f"{label} · direct reviewed purpose and format match · {peer}"
    if tier == 2:
        return f"{label} · transferable example with a registered adaptation · {peer}"
    return f"{label} · potential match; review or context is incomplete · {peer}"
