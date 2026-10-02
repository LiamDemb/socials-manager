"""Broad temporal window analysis with confounding disclosure."""
from collections import defaultdict

from intelligence.analysis import STATUS_INSUFFICIENT, STATUS_READY


def run(spec, request: dict, ctx: dict) -> dict:
    posts = ctx.get("timed_posts") or []
    cfg = spec.config or {}
    min_posts = cfg.get("min_posts", 6)
    if not posts:
        return {"status": STATUS_INSUFFICIENT, "detail": "No timed posts", "sample_size": 0}
    buckets = defaultdict(list)
    confounded = False
    for p in posts:
        wd = p.get("weekday")
        hr = p.get("hour")
        if wd is None or hr is None:
            continue
        key = (wd, hr)
        buckets[key].append(float(p.get("response") or 0))
        if len({p.get("format") for p in posts if p.get("weekday") == wd}) > 1:
            confounded = True
    if len(posts) < min_posts:
        return {
            "status": STATUS_INSUFFICIENT,
            "detail": f"Need {min_posts} timed posts",
            "sample_size": len(posts),
        }
    ranked = sorted(
        ((k, sum(v) / len(v), len(v)) for k, v in buckets.items() if v),
        key=lambda x: -x[1],
    )
    best = ranked[0] if ranked else None
    timing = None
    if best:
        timing = {
            "preferred_hour": best[0][1],
            "window": f"{best[0][1]:02d}:00-{(best[0][1] + 2) % 24:02d}:00",
            "refs": [{"kind": "temporal_bucket", "n": best[2]}],
            "sample_n": best[2],
            "limitation": "Day and hour may be confounded" if confounded else "",
        }
    return {
        "status": STATUS_READY,
        "timing_evidence": timing,
        "descriptive": {"buckets": len(buckets), "confounded": confounded},
        "proposition": "Broad posting window from observed timed posts",
    }
