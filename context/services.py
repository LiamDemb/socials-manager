from core import clock
from core.services import audit

from .models import InspirationReference, PeerProfile, ReviewedContextItem


def ensure_default_peers():
    """Curated peer list is owner-reviewed, not scraped."""
    if PeerProfile.objects.exists():
        return
    PeerProfile.objects.create(
        handle="example_peer",
        label="Example peer (fixture)",
        review_state="reviewed",
        notes="Synthetic fixture peer for tests. Replace with owner-reviewed cohort.",
        capability={"route": "fixture", "live_collection": "blocked"},
        created_at=clock.now(),
        reviewed_at=clock.now(),
    )


def add_inspiration(title, url="", excerpt="", scope="global", scope_ref=""):
    ref = InspirationReference.objects.create(
        scope=scope,
        scope_ref=scope_ref,
        title=title,
        url=url,
        excerpt=excerpt,
        retrieved_at=clock.now(),
    )
    audit("inspiration", ref.pk, "attach", {"scope": scope})
    return ref
