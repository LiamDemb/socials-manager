"""Process an owner-created image without consulting Instagram source policy."""
import hashlib
import io
import struct

from core import clock
from intelligence.clip_adapter import ENCODER_ID, encode_rgb, status as clip_status
from intelligence.content_registry import CONTENT_FEATURES, PURPOSE_VALUES
from intelligence.gemma_adapter import status as gemma_status

from .content_features import run_extraction_pipeline
from .media_storage import store_blob
from .models import ContentEmbedding, ContentFeatureValue, MediaAsset, MediaPack, PeerMedia, PeerProfile
from .visual_descriptors import compute_visual_descriptors


def ingest_owner_image(png_bytes: bytes, *, caption: str) -> dict:
    """Store, describe, and embed a local PNG. The caller must already know the file is owner-made."""
    from PIL import Image

    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    width, height = image.size
    pixels = list(image.getdata())
    digest, rel = store_blob(png_bytes, ext="png", kind="preview")
    peer, _created = PeerProfile.objects.get_or_create(
        label="Owner library",
        defaults={
            "review_state": "reviewed",
            "peer_role": "reference_only",
            "created_at": clock.now(),
            "reviewed_at": clock.now(),
            "notes": "Local owner-created assets. Not an Instagram peer and not in the comparable analysis cohort.",
        },
    )
    if peer.review_state != "reviewed" or peer.peer_role != "reference_only":
        peer.review_state = "reviewed"
        peer.peer_role = "reference_only"
        peer.reviewed_at = peer.reviewed_at or clock.now()
        peer.save(update_fields=["review_state", "peer_role", "reviewed_at"])
    post = PeerMedia.objects.create(
        peer=peer,
        provider_namespace="local",
        external_id=digest[:32],
        caption=caption[:4000],
        media_type="IMAGE",
        media_availability="partial",
        snapshot={"origin": "owner_upload", "content_hash": digest},
        collected_at=clock.now(),
    )
    MediaAsset.objects.create(
        post=post,
        role="preview",
        content_hash=digest,
        relative_path=rel,
        mime_type="image/png",
        byte_size=len(png_bytes),
        width=width,
        height=height,
        captured_at=clock.now(),
        retention_class="analysis_derivative",
    )
    unit = [(r / 255.0, g / 255.0, b / 255.0) for r, g, b in pixels]
    descriptors = compute_visual_descriptors(unit, "srgb")
    for key, value in (
        ("mean_luminance", descriptors.get("mean_luminance")),
        ("mean_saturation", descriptors.get("saturation_mean")),
    ):
        if value is None:
            continue
        ContentFeatureValue.objects.create(
            post=post,
            feature_key=key,
            feature_version=CONTENT_FEATURES[key]["version"],
            value_json={"value": value},
            review_state="accepted",
            support=[{"kind": "measured_pixels", "asset_hash": digest}],
            origin="deterministic",
            created_at=clock.now(),
        )
    pack = MediaPack.objects.create(
        post=post,
        input_hash=digest[:32],
        state="partial",
        reason="owner_image",
        sampling_manifest={"coverage": "full_image", "schema_version": "owner-image-v1"},
        stored_bytes=len(png_bytes),
        created_at=clock.now(),
        completed_at=clock.now(),
    )
    run = run_extraction_pipeline(post, pack)
    proposed = _propose_caption_purpose(post)
    return {
        "post_id": str(post.pk),
        "pack_id": str(pack.pk),
        "asset_hash": digest,
        "descriptors": {
            "mean_luminance": descriptors.get("mean_luminance"),
            "saturation_mean": descriptors.get("saturation_mean"),
            "status": descriptors.get("status"),
        },
        "proposed_purpose": proposed,
        "extraction_run_id": str(run.pk),
        "embedding": _embed(post, pixels, width, height),
        "clip": clip_status(),
        "gemma": gemma_status(),
        "instagram_policy_consulted": False,
    }


def _propose_caption_purpose(post: PeerMedia):
    caption = (post.caption or "").lower()
    for value in PURPOSE_VALUES:
        token = value.replace("_", " ")
        if token in caption or value in caption:
            ContentFeatureValue.objects.create(
                post=post,
                feature_key="reviewed_purpose",
                feature_version=CONTENT_FEATURES["reviewed_purpose"]["version"],
                value_json={"value": value},
                review_state="suggested",
                support=[{"kind": "caption_span", "text": token}],
                origin="extraction",
                created_at=clock.now(),
            )
            return value
    return None


def _embed(post, pixels, width, height) -> dict:
    report = clip_status()
    if report.get("state") != "importable":
        return {"state": "unavailable", "reason": report.get("reason"), "owner_action": report.get("owner_action")}
    encoded = encode_rgb(pixels, width, height)
    blob = struct.pack(f"<{len(encoded['vector'])}f", *encoded["vector"])
    row = ContentEmbedding.objects.create(
        post=post,
        encoder_version=ENCODER_ID,
        dimensions=encoded["dimensions"],
        vector_blob=blob,
        vector_hash=hashlib.sha256(blob).hexdigest(),
        frame_role="image",
        created_at=clock.now(),
    )
    return {"state": "stored", "id": str(row.pk), "encoder": ENCODER_ID, "dimensions": encoded["dimensions"]}
