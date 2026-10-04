"""post-age-7d-v1 snapshot selection (M08/M11)."""
from datetime import timedelta

from context.models import PeerMedia, PeerMediaMetricSnapshot

TARGET_HOURS = 168
WINDOW = (156, 180)


def select_snapshot_at_age(post: PeerMedia, as_of=None):
    if not post.published_at:
        return None, "no_publication_time"
    from core import clock

    as_of = as_of or clock.now()
    target = post.published_at + timedelta(hours=TARGET_HOURS)
    snaps = list(post.metric_snapshots.order_by("captured_at"))
    if not snaps:
        return None, "no_snapshots"
    best = None
    best_delta = None
    for s in snaps:
        if s.captured_at > as_of:
            continue
        age_h = (s.captured_at - post.published_at).total_seconds() / 3600
        if age_h < WINDOW[0] or age_h > WINDOW[1]:
            continue
        delta = abs(age_h - TARGET_HOURS)
        if best is None or delta < best_delta or (delta == best_delta and s.captured_at < best.captured_at):
            best = s
            best_delta = delta
    if not best:
        return None, "insufficient_age_snapshots"
    return best, None
