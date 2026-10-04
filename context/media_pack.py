"""ensure_media_pack: acquisition revision + job enqueue (M03/M04)."""
import hashlib
import json

from core import clock
from core.services import enqueue

from .media_capability import resolve_media_capability
from .media_config import PROFILE_VERSION
from .models import MediaPack, PeerMedia


def _input_hash(post: PeerMedia) -> str:
    body = {
        "post_id": str(post.pk),
        "revision": post.acquisition_revision,
        "snapshot": post.snapshot,
        "profile": PROFILE_VERSION,
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:32]


def ensure_media_pack(post_id, profile_version=PROFILE_VERSION, reprocess=False):
    post = PeerMedia.objects.get(pk=post_id)
    cap = resolve_media_capability(post, "media_acquire_cache")
    if cap["state"] == "denied":
        post.media_availability = "restricted"
        post.save(update_fields=["media_availability"])
        return {"state": "blocked", "reason": cap["reason"]}
    if cap["state"] == "unknown":
        post.media_availability = "link_only"
        post.save(update_fields=["media_availability"])
        return {"state": "link_only", "reason": cap.get("reason")}
    ih = _input_hash(post)
    pack, created = MediaPack.objects.get_or_create(
        post=post,
        profile_version=profile_version,
        input_hash=ih,
        defaults={"state": "queued", "created_at": clock.now()},
    )
    if pack.state == "ready" and not reprocess:
        return {"state": "ready", "pack_id": str(pack.pk)}
    post.media_availability = "queued"
    post.save(update_fields=["media_availability"])
    enqueue("media.process", scope_key=str(post.pk), input_key=ih)
    return {"state": "queued", "pack_id": str(pack.pk), "created": created}


def run_media_process_job(post_id: str, input_key: str):
    """Worker: caption/descriptor path without unbounded download when no asset URL."""
    from .content_features import run_extraction_pipeline
    from .visual_descriptors import build_caption_only_manifest

    post = PeerMedia.objects.get(pk=post_id)
    pack = MediaPack.objects.filter(post=post, input_hash=input_key).first()
    if not pack:
        return {"state": "missing_pack"}
    pack.state = "analysing"
    pack.save(update_fields=["state"])
    post.media_availability = "analysing"
    post.save(update_fields=["media_availability"])
    from .visual_descriptors import compute_video_frame_targets

    duration = (post.snapshot or {}).get("duration_seconds")
    if duration:
        manifest = compute_video_frame_targets(float(duration))
        manifest["coverage"] = "sampled_frames" if manifest.get("frames") else "caption_only"
    else:
        manifest = build_caption_only_manifest(post)
    pack.sampling_manifest = manifest
    pack.state = "partial" if manifest.get("coverage") != "full" else "ready"
    pack.completed_at = clock.now()
    pack.save()
    run_extraction_pipeline(post, pack)
    post.media_availability = pack.state
    post.save(update_fields=["media_availability"])
    return {"state": pack.state, "pack_id": str(pack.pk)}
