"""Read-only content inspection (M11/§14). No acquisition side effects."""
from context.models import ContentFeatureValue, MediaPack, PeerMedia
from context.media_labels import display_media_type


def inspect_peer_media(peer_media_id) -> dict:
    media = PeerMedia.objects.select_related("peer").get(pk=peer_media_id)
    pack = MediaPack.objects.filter(post=media).order_by("-created_at").first()
    features = (
        ContentFeatureValue.objects.filter(post=media)
        .order_by("feature_key", "-created_at")
        .distinct()[:40]
    )
    return {
        "peer_media_id": str(media.pk),
        "peer_label": media.peer.label,
        "media_type": media.media_type,
        "media_type_display": display_media_type(media.media_type),
        "media_availability": media.media_availability or "link_only",
        "permalink": media.permalink or "",
        "caption_excerpt": (media.caption or "")[:500],
        "pack": (
            {
                "state": pack.state,
                "reason": pack.reason,
                "profile_version": pack.profile_version,
                "input_hash": pack.input_hash,
            }
            if pack
            else None
        ),
        "features": [
            {
                "feature_key": f.feature_key,
                "review_state": f.review_state,
                "value": (f.value_json or {}).get("value"),
            }
            for f in features
        ],
    }
