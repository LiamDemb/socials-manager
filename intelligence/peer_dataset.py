"""Build analysis dataset rows from stored PeerMedia and metric snapshots."""
import hashlib
import json

from context.models import PeerMedia, PeerMediaMetricSnapshot, PeerProfile
from context.roles import ANALYSIS_COMPARABLE_ROLES

DATASET_VERSION = "peer-posts-v1"
MAX_ANALYSIS_POSTS = 500


def _response_metric(media: PeerMedia) -> tuple[float | None, str, float | None]:
    """Public likes only. Comments stay a separate field and are not added in."""
    from intelligence.peer_snapshots import select_snapshot_at_age

    snap, _reason = select_snapshot_at_age(media)
    if snap and snap.metrics.get("like_count") is not None:
        comments = snap.metrics.get("comments_count")
        return float(snap.metrics["like_count"]), "post-age-7d-v1", None if comments is None else float(comments)
    raw = media.snapshot or {}
    if raw.get("like_count") is not None:
        comments = raw.get("comments_count")
        return float(raw["like_count"]), "capture_public_likes", None if comments is None else float(comments)
    latest = media.metric_snapshots.order_by("-captured_at").first()
    if latest and latest.metrics.get("like_count") is not None:
        comments = latest.metrics.get("comments_count")
        return float(latest.metrics["like_count"]), "latest_snapshot_not_7d", None if comments is None else float(comments)
    return None, "no_public_likes", None


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
    seen = set()
    for m in media_qs:
        if m.pk in seen:
            continue
        seen.add(m.pk)
        response, basis, comments = _response_metric(m)
        fmt = (m.media_type or "unknown").lower()
        if response is None:
            exclusions.append({"media_id": str(m.pk), "reason": "no_public_metrics_at_capture"})
            continue
        from context.models import ContentFeatureValue

        features = {}
        for fv in ContentFeatureValue.objects.filter(post=m).order_by("feature_key", "-created_at"):
            if fv.feature_key in features:
                continue
            if fv.review_state in ("accepted", "corrected") or fv.feature_key in ("mean_luminance", "mean_saturation"):
                features[fv.feature_key] = (fv.value_json or {}).get("value")
        post_rows.append(
            {
                "peer_media_id": str(m.pk),
                "peer_id": str(m.peer_id),
                "peer_label": m.peer.label,
                "format": fmt,
                "response": response,
                "response_basis": basis,
                "public_comments": comments,
                "features": features,
                "frame_count": m.assets.filter(role="analysis_frame").count(),
                "published_at": m.published_at.isoformat() if m.published_at else None,
                "collected_at": m.collected_at.isoformat(),
                "measurement_note": "Public likes only. Not a sum with comments, reach, or conversions.",
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
