"""Fair extraction selection. A few active peers must not take every slot."""

from collections import defaultdict

from .models import PeerMedia


def select_extraction_batch(limit: int = 10) -> list[PeerMedia]:
    pending = (
        PeerMedia.objects.filter(
            media_availability__in=["link_only", "queued", "failed", "partial"]
        )
        .select_related("peer")
        .order_by("collected_at")
    )
    buckets = defaultdict(list)
    for media in pending:
        buckets[str(media.peer_id)].append(media)
    if not buckets:
        return []
    ordered = []
    keys = sorted(buckets)
    while len(ordered) < limit and any(buckets.values()):
        for key in keys:
            if buckets[key] and len(ordered) < limit:
                ordered.append(buckets[key].pop(0))
    return ordered
