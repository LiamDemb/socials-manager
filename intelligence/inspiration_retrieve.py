"""Structured + text retrieval over eligible universe (M06)."""
import re
import sqlite3

from django.db import connection

from context.library import explore_media_queryset, media_card
from context.models import ContentFeatureValue, InspirationReference
from context.roles import CREATIVE_EXPLORE_ROLES

MAX_PER_ROUTE = 100
MAX_UNION = 300


def _structured_candidates(request_payload: dict) -> list[dict]:
    purpose = (request_payload.get("purpose") or "").lower()
    channel = (request_payload.get("channel") or "").lower()
    fmt = (request_payload.get("format") or "").lower()
    scored = []
    for media in explore_media_queryset()[:MAX_PER_ROUTE]:
        card = media_card(media)
        score = 0
        if purpose and purpose in (media.caption or "").lower():
            score += 5
        if channel and card["channel"] == channel:
            score += 2
        if fmt and fmt in (media.media_type or "").lower():
            score += 2
        accepted = (
            ContentFeatureValue.objects.filter(
                post=media, feature_key="reviewed_purpose", review_state__in=("accepted", "corrected")
            )
            .order_by("-created_at")
            .first()
        )
        if accepted:
            card["reviewed_purpose"] = str(accepted.value_json.get("value", "")).lower()
        if accepted and purpose and card.get("reviewed_purpose") == purpose:
            score += 5
        if score > 0:
            card["structured_score"] = score
            scored.append(card)
    scored.sort(key=lambda c: (-c.get("structured_score", 0), c.get("published_at") or ""), reverse=False)
    scored.sort(key=lambda c: -c.get("structured_score", 0))
    return scored


def _fts_candidates(request_payload: dict) -> list[dict]:
    q_terms = []
    for key in ("purpose", "format", "channel"):
        v = request_payload.get(key)
        if v:
            q_terms.append(str(v))
    if not q_terms:
        return []
    query = " ".join(q_terms)
    # Build ephemeral FTS over captions in Python/SQLite for current scale.
    cards = []
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT sqlite_version()")
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE post_fts USING fts5(peer_media_id, caption)")
        for media in explore_media_queryset()[:MAX_PER_ROUTE]:
            conn.execute("INSERT INTO post_fts(peer_media_id, caption) VALUES (?,?)", (str(media.pk), media.caption or ""))
        tokens = [t for t in re.findall(r"[A-Za-z0-9_]+", query) if t]
        if not tokens:
            conn.close()
            return []
        match = " OR ".join(tokens)
        rows = conn.execute(
            "SELECT peer_media_id, bm25(post_fts) AS rank FROM post_fts WHERE post_fts MATCH ? ORDER BY rank LIMIT ?",
            (match, MAX_PER_ROUTE),
        ).fetchall()
        from context.models import PeerMedia

        for mid, rank in rows:
            media = PeerMedia.objects.filter(pk=mid).select_related("peer").first()
            if media:
                card = media_card(media)
                card["fts_rank"] = rank
                cards.append(card)
        conn.close()
    except sqlite3.OperationalError:
        return []
    return cards


def _visual_candidates(request_payload: dict) -> tuple[list[dict], str]:
    from intelligence.clip_adapter import rank_vectors, status

    report = status()
    query = request_payload.get("visual_query")
    if report["state"] == "unavailable":
        return [], f"embedding_unavailable: {report['reason']}"
    if not query:
        return [], "embedding_unavailable: no query vector on this request. Text and structured routes still run. Encode with the CLIP adapter before asking for visual rank."
    from context.models import ContentEmbedding, PeerMedia

    items = []
    for emb in ContentEmbedding.objects.filter(encoder_version=report["encoder"]).select_related("post", "post__peer")[:100]:
        import struct

        count = len(emb.vector_blob) // 4
        if count != emb.dimensions:
            continue
        vec = list(struct.unpack(f"<{count}f", bytes(emb.vector_blob)))
        media = emb.post
        card = media_card(media) if isinstance(media, PeerMedia) else {"id": str(emb.post_id)}
        card["vector"] = vec
        items.append(card)
    if not items:
        return [], "embedding_unavailable: CLIP imports, but no stored vectors exist for this encoder."
    ranked = rank_vectors(list(query), items)
    return ranked, ""


def retrieve_candidates(request_payload: dict) -> dict:
    structured = _structured_candidates(request_payload)
    fts = _fts_candidates(request_payload)
    visual, visual_gap = _visual_candidates(request_payload)
    by_id = {}
    for route, items in (("structured", structured), ("fts", fts), ("visual", visual)):
        for idx, card in enumerate(items, start=1):
            cid = card.get("id")
            if cid not in by_id:
                by_id[cid] = {**card, "routes": {}}
            by_id[cid]["routes"][route] = idx
            if "vector" in by_id[cid]:
                by_id[cid].pop("vector", None)
    union = list(by_id.values())[:MAX_UNION]
    gaps = []
    if visual_gap:
        gaps.append(visual_gap)
    return {"candidates": union, "gaps": gaps, "route_counts": {"structured": len(structured), "fts": len(fts), "visual": len(visual)}}
