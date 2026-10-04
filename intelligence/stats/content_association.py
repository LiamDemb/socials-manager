"""Scoped content contrasts on already-built post rows (section 11). Not a new model family."""
from collections import defaultdict


def contrast(rows: list[dict], feature_key: str, spec_config: dict | None = None) -> dict:
    cfg = spec_config or {}
    min_level = cfg.get("min_per_level", 10)
    deduped = {}
    for row in rows:
        pid = row.get("peer_media_id")
        if not pid or pid in deduped:
            continue
        deduped[pid] = row
    groups = defaultdict(list)
    artists = defaultdict(set)
    for row in deduped.values():
        if row.get("response_basis") != "post-age-7d-v1":
            continue
        value = (row.get("features") or {}).get(feature_key)
        if value is None or value == "unknown":
            continue
        key = str(value)
        groups[key].append(float(row.get("response") or 0))
        artists[key].add(row.get("peer_id"))
    if len(groups) < 2 or any(len(vals) < min_level for vals in groups.values()):
        return {
            "status": "insufficient_data",
            "feature_key": feature_key,
            "detail": "Compared levels need the configured minimum of distinct 7-day posts.",
            "levels": {k: len(v) for k, v in groups.items()},
        }
    artist_sets = [a for a in artists.values() if a]
    if artist_sets and all(len(a) == 1 for a in artist_sets) and len({next(iter(a)) for a in artist_sets}) > 1:
        return {
            "status": "blocked",
            "blocker_code": "confounded_artist",
            "feature_key": feature_key,
            "detail": "Each compared level is a single different artist, so the feature is not separable.",
        }
    summary = {k: {"n": len(v), "mean": sum(v) / len(v)} for k, v in groups.items()}
    return {
        "status": "descriptive_only",
        "feature_key": feature_key,
        "proposition": f"Descriptive {feature_key} contrast at post-age-7d-v1 public likes",
        "groups": summary,
        "support": "descriptive",
        "detail": "Not a qualified causal or transferable finding.",
    }
