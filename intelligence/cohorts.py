"""Cohort membership for analysis (excludes manual inspiration)."""
import hashlib
import json

from core import clock

from context.models import InspirationReference, PeerMedia, PeerProfile

COHORT_POLICY_VERSION = "cohort-v1"


def build_comparable_cohort() -> dict:
    peers = list(
        PeerProfile.objects.filter(review_state="reviewed", peer_role="comparable").values_list("pk", flat=True)
    )
    media_ids = list(
        PeerMedia.objects.filter(peer_id__in=peers).values_list("external_id", flat=True)[:500]
    )
    manual_inspiration = list(
        InspirationReference.objects.filter(in_analytical_pool=False).values_list("pk", flat=True)[:20]
    )
    body = {
        "policy": COHORT_POLICY_VERSION,
        "peers": [str(p) for p in peers],
        "media_external_ids": media_ids,
        "excluded_manual_inspiration": [str(i) for i in manual_inspiration],
    }
    fp = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:32]
    from .models import CohortVersion

    cv, _ = CohortVersion.objects.get_or_create(
        fingerprint=fp,
        defaults={"policy_version": COHORT_POLICY_VERSION, "membership": body, "created_at": clock.now()},
    )
    return {"fingerprint": fp, "membership": body, "id": str(cv.pk), "stale": cv.stale}


def invalidate_cohort_for_peer(peer_id):
    from .lineage import mark_fits_stale

    CohortVersion.objects.filter(membership__peers__contains=str(peer_id)).update(stale=True)
    mark_fits_stale("peer_excluded_or_role_changed")
