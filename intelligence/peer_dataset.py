"""Build analysis dataset rows from stored PeerMedia and metric snapshots."""
import hashlib
import json

from context.models import PeerMedia, PeerMediaMetricSnapshot, PeerProfile
from context.roles import ANALYSIS_COMPARABLE_ROLES

DATASET_VERSION = "peer-posts-v1"
MAX_ANALYSIS_POSTS = 500


def _response_metric(media: PeerMedia) -> float | None:
    snap = media.snapshot or {}
    likes = snap.get("like_count")
    comments = snap.get("comments_count")
    if likes is None and comments is None:
        latest = media.metric_snapshots.first()
        if latest:
            likes = latest.metrics.get("like_count")
            comments = latest.metrics.get("comments_count")
    if likes is None and comments is None:
        return None
    return float(likes or 0) + float(comments or 0)


def build_peer_post_dataset(metric_id: str | None = None) -> dict:
    peers = list(
        PeerProfile.objects.filter(review_state="reviewed", peer_role__in=ANALYSIS_COMPARABLE_ROLES).values_list(
            "pk", flat=True
        )
    )
    media_qs = (
        PeerMedia.objects.filter(peer_id__in=peers)
        .select_related("peer")
        .order_by("-published_at", "-collected_at")[:MAX_ANALYSIS_POSTS]
    )
    post_rows = []
    exclusions = []
    for m in media_qs:
        response = _response_metric(m)
        fmt = (m.media_type or "unknown").lower()
        if response is None:
            exclusions.append({"media_id": str(m.pk), "reason": "no_public_metrics_at_capture"})
            continue
        post_rows.append(
            {
                "peer_media_id": str(m.pk),
                "peer_id": str(m.peer_id),
                "peer_label": m.peer.label,
                "format": fmt,
                "response": response,
                "published_at": m.published_at.isoformat() if m.published_at else None,
                "collected_at": m.collected_at.isoformat(),
                "measurement_note": "Public interaction counts at collection; not private reach or conversions.",
            }
        )
    body = {
        "version": DATASET_VERSION,
        "metric_id": metric_id or "",
        "peer_ids": [str(p) for p in peers],
        "post_count": len(post_rows),
        "excluded": exclusions[:50],
        "cap": MAX_ANALYSIS_POSTS,
    }
    dataset_hash = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:32]
    return {
        "post_rows": post_rows,
        "dataset_hash": f"peer-posts:{dataset_hash}",
        "dataset_meta": body,
        "cohort": {"peer_ids": body["peer_ids"], "analytical_roles": list(ANALYSIS_COMPARABLE_ROLES)},
    }


def enrich_analysis_ctx(ctx: dict) -> dict:
    ds = build_peer_post_dataset(ctx.get("primary_metric_id"))
    base = ctx.get("dataset_hash") or "dataset-empty"
    return {**ctx, **ds, "dataset_hash": f"{base}|{ds['dataset_hash']}"}
