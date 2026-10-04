"""Source-purpose checks for media operations (M02)."""
from sources.models import Source
from sources.services import current_policy

OPERATIONS = (
    "media_acquire_cache",
    "feature_extract_deterministic",
    "feature_extract_multimodal",
    "embedding_generate",
    "statistical_fit",
    "llm_synthesis",
)

PURPOSE_MAP = {
    "media_acquire_cache": "descriptive_derive",
    "feature_extract_deterministic": "descriptive_derive",
    "feature_extract_multimodal": "llm_ingest",
    "embedding_generate": "descriptive_derive",
    "statistical_fit": "statistical_fit",
    "llm_synthesis": "llm_ingest",
}


def purpose_state(provider: str, purpose: str) -> tuple[str, str]:
    """Map a stored purpose to allowed, denied, or unknown. Unresolved is unknown."""
    source = Source.objects.filter(provider=provider, state="active").order_by("revision").first()
    if not source or not source.policies.exists():
        return "unknown", "no_policy"
    raw = (current_policy(source).purposes or {}).get(purpose) or "unresolved"
    if raw == "allowed":
        return "allowed", raw
    if raw == "denied":
        return "denied", raw
    return "unknown", raw


def resolve_media_capability(post, operation: str) -> dict:
    """Return allowed | denied | unknown for a canonical post and operation."""
    if operation not in OPERATIONS:
        return {"state": "denied", "reason": "unknown_operation"}
    purpose = PURPOSE_MAP.get(operation, "descriptive_derive")
    snap = post.snapshot or {}
    media_url = snap.get("media_url") or snap.get("thumbnail_url")
    thumb_only = bool(snap.get("thumbnail_url") and not snap.get("media_url"))
    if operation == "media_acquire_cache":
        if not media_url and not thumb_only and not post.permalink:
            return {
                "state": "unknown",
                "reason": "caption_permalink_only",
                "detail": "No allowlisted asset URL; caption/text path only.",
            }
    state, raw = purpose_state("instagram", purpose)
    if state != "allowed":
        return {
            "state": state,
            "reason": "source_purpose_denied" if state == "denied" else "source_use_unknown",
            "purpose": purpose,
            "stored_purpose": raw,
        }
    if thumb_only and operation in ("feature_extract_multimodal", "embedding_generate"):
        return {
            "state": "allowed",
            "reason": "thumbnail_only",
            "detail": "Thumbnail only; no whole-video or audio claims.",
            "supported_fields": ["thumbnail_image"],
        }
    return {
        "state": "allowed",
        "reason": "ok",
        "purpose": purpose,
        "assessment_ref": "instagram_policy_v1",
        "retention": "compact derivatives under the data root; originals are transient",
    }


def provider_capability_report() -> dict:
    """Never treat configured credentials as certified media or caching permission."""
    import os

    token_present = bool(os.environ.get("META_ACCESS_TOKEN"))
    return {
        "provider": "instagram",
        "api": "graph",
        "certified": False,
        "token_configured": token_present,
        "peer_video_acquisition": "unknown",
        "caching_for_inference": "unknown",
        "reason": "A configured token does not certify Business Discovery, caching, or permission to analyse media.",
        "owner_action": "Run sources.meta_graph.probe_media_fields. Peer video needs a current Page-linked META_ACCESS_TOKEN. Set each Instagram purpose to allowed before acquisition, embedding, or inference.",
    }
