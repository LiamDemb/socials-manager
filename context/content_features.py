"""Extract and review content features (M04/M07)."""
from core import clock

from .models import ContentAnalysisRun, ContentFeatureValue, MediaPack, PeerMedia
from intelligence.content_registry import CONTENT_FEATURES


def run_extraction_pipeline(post: PeerMedia, pack: MediaPack):
    """Deterministic caption-derived proposals; multimodal adapter queued separately."""
    from intelligence.extraction_adapter import extract_labels

    started = clock.now()
    from intelligence.extraction_validate import validate_extraction

    outcome = extract_labels(post, pack)
    known = {str(a.pk) for a in post.assets.all()}
    checked = validate_extraction(outcome, known_asset_ids=known)
    outcome = {**outcome, "fields": checked["fields"]}
    output = dict(outcome.get("output") or {})
    output["rejected_fields"] = checked["rejected"]
    output["description"] = checked["description"]
    outcome["output"] = output
    run = ContentAnalysisRun.objects.create(
        pack=pack,
        adapter=outcome.get("adapter", "deterministic-caption-v1"),
        model_revision=outcome.get("model_revision", "none"),
        schema_version=outcome.get("schema_version", "content-labels-v1"),
        status=outcome.get("status", "ready"),
        reason=outcome.get("reason", ""),
        output=outcome.get("output", {}),
        input_hash=pack.input_hash,
        elapsed_ms=outcome.get("elapsed_ms", 0),
        created_at=started,
    )
    for field in outcome.get("fields") or []:
        key = field.get("feature_key")
        if key not in CONTENT_FEATURES:
            continue
        ContentFeatureValue.objects.create(
            post=post,
            feature_key=key,
            feature_version=CONTENT_FEATURES[key]["version"],
            value_json={"value": field.get("value")},
            review_state="suggested",
            support=field.get("support") or [],
            origin="extraction",
            source_run=run,
            created_at=clock.now(),
        )
    return run


def review_features(post_id, decisions: list[dict], expected_revision: int | None = None):
    from core.errors import DomainError

    from .media_invalidation import invalidate_for_label_correction

    post = PeerMedia.objects.get(pk=post_id)
    updated = 0
    for d in decisions:
        fv = ContentFeatureValue.objects.filter(post=post, feature_key=d["feature_key"]).order_by("-created_at").first()
        if not fv:
            continue
        if expected_revision is not None and fv.review_revision != expected_revision:
            raise DomainError("stale_review", "Reload the review; this field changed.", status=409)
        state = d.get("review_state", "accepted")
        if state not in ("suggested", "accepted", "corrected", "rejected", "unknown"):
            raise DomainError("invalid_review_state", "Unknown review state.")
        value = d["value"] if d.get("value") is not None else (fv.value_json or {}).get("value")
        ContentFeatureValue.objects.create(
            post=post,
            feature_key=fv.feature_key,
            feature_version=fv.feature_version,
            value_json={"value": value, "supersedes": str(fv.pk)},
            review_state=state,
            review_revision=fv.review_revision + 1,
            support=fv.support,
            origin="review",
            source_run=fv.source_run,
            created_at=clock.now(),
        )
        updated += 1
    if updated:
        invalidate_for_label_correction(str(post.pk))
    return updated
