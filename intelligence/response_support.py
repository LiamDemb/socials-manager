"""Descriptive public-likes support for ranking (section 11). Comments are not a substitute."""
from datetime import timedelta

from django.core.exceptions import ValidationError

from context.models import PeerMedia

from .peer_snapshots import select_snapshot_at_age

METRIC_ID = "public_like_count"
METRIC_VERSION = "post-age-7d-v1"


def performance_adjustment(card: dict, mode: str = "best_fit") -> tuple[float, str, str]:
    """Return (B, reason, pathway). Unknown support is B=0. Do not add a second pathway."""
    try:
        media = PeerMedia.objects.select_related("peer").get(pk=card["id"])
    except (PeerMedia.DoesNotExist, ValidationError, ValueError, TypeError):
        return 0.0, "Unknown response support.", "none"
    snap, reason = select_snapshot_at_age(media)
    if not snap:
        return 0.0, f"No 7-day public likes snapshot ({reason}).", "none"
    likes = (snap.metrics or {}).get("like_count")
    if likes is None:
        return 0.0, "Public likes were not captured on the 7-day snapshot.", "none"
    if not media.published_at:
        return 0.0, "Publication time is missing, so age cannot be checked.", "none"
    baseline_posts = PeerMedia.objects.filter(
        peer=media.peer,
        media_type=media.media_type,
        published_at__lt=media.published_at,
        published_at__gte=media.published_at - timedelta(days=180),
    ).exclude(pk=media.pk)[:200]
    vals = []
    ids = []
    for post in baseline_posts:
        other, _ = select_snapshot_at_age(post)
        if not other or other.metrics.get("like_count") is None:
            continue
        vals.append(float(other.metrics["like_count"]))
        ids.append(str(post.pk))
    if len(vals) < 10:
        return 0.0, "Baseline sample below minimum (10 distinct posts).", "none"
    value = float(likes)
    count_less = sum(1 for v in vals if v < value)
    count_equal = sum(1 for v in vals if v == value)
    percentile = (count_less + 0.5 * count_equal) / len(vals)
    adjustment = 0.10 * (percentile - 0.5)
    cap = 0.10 if mode == "strong_public_response" else 0.05
    adjustment = max(-cap, min(cap, adjustment))
    text = (
        f"Public likes ({METRIC_ID}/{METRIC_VERSION}) percentile {percentile:.2f} "
        f"within this artist and format, n={len(ids)}. Descriptive position, not a chance of success."
    )
    return adjustment, text, "historical_percentile"
