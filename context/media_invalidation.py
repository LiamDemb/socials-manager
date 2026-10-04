"""Invalidation hooks for media/intelligence dependencies (section 13)."""
from intelligence.lineage import mark_fits_stale


def invalidate_for_label_correction(post_id: str):
    mark_fits_stale("label_correction", cohort_fingerprint=None)
    return {"post_id": post_id, "visual_extraction_rerun": False, "fits": "stale"}


def invalidate_for_metric_snapshot(post_id: str):
    mark_fits_stale("metric_snapshot", cohort_fingerprint=None)
    return {"post_id": post_id, "visual_extraction_rerun": False}


def invalidate_for_peer_role(peer_id: str):
    mark_fits_stale("peer_role", cohort_fingerprint=None)
    return {"peer_id": peer_id}


def invalidate_for_policy_revocation(post_id: str):
    from .models import PeerMedia

    PeerMedia.objects.filter(pk=post_id).update(media_availability="restricted")
    mark_fits_stale("source_policy", cohort_fingerprint=None)
    return {"post_id": post_id, "media_availability": "restricted"}


def invalidate_for_eviction(post_id: str):
    from .models import PeerMedia

    PeerMedia.objects.filter(pk=post_id).update(media_availability="evicted")
    return {"post_id": post_id, "features_retained": True}


def note_preference_only_save(reference_id: str):
    """Bookmarks do not stale numerical fits."""
    return {"reference_id": reference_id, "fits_invalidated": False}
