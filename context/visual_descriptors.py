"""Deterministic visual-descriptors-v1 and sampling manifests (sections 5–6)."""
import math
import random

from .media_config import DESCRIPTOR_VERSION, LIMITS, SAMPLING_SCHEMA

HUE_SECTORS = 6
PALETTE_CENTROIDS = 5
CLUSTER_SEED = 1
LOW_SATURATION = 0.10
MAX_SAMPLE_PIXELS = 400


def build_caption_only_manifest(post) -> dict:
    return {
        "schema_version": SAMPLING_SCHEMA,
        "coverage": "caption_only",
        "known_format": post.media_type or "unknown",
        "note": "No permitted compact asset acquired; text/caption path only.",
        "frames": [],
        "children_selected": [],
        "children_omitted": [],
        "colour_handling": "unavailable",
        "temporal": {"cut_rate": None, "motion": None, "beat_sync": None, "reason": "detector_unqualified"},
    }


def compute_video_frame_targets(duration_seconds: float) -> list[dict]:
    """Opening plus uniform midpoints. Merge within 0.1s. Do not pad to eight."""
    raw = float(duration_seconds or 0)
    inspected = min(max(raw, 0.0), float(LIMITS["decode_max_seconds"]))
    partial = raw > LIMITS["decode_max_seconds"]
    openings = [t for t in (0.0, 0.5, 1.5) if t <= inspected]
    mids = [(j + 0.5) * inspected / 5.0 for j in range(5)] if inspected > 0 else [0.0]
    points = [(t, {"hook_opening"}) for t in openings] + [(t, {"palette_uniform"}) for t in mids]
    points.sort(key=lambda item: item[0])
    merged = []
    for t, roles in points:
        if merged and abs(t - merged[-1]["target_seconds"]) <= 0.1:
            merged[-1]["roles"] = sorted(set(merged[-1]["roles"]) | roles)
            continue
        merged.append({"target_seconds": round(t, 3), "roles": sorted(roles), "actual_seconds": None})
    cap = LIMITS["video_frames_max"]
    frames = merged[:cap]
    return {
        "schema_version": SAMPLING_SCHEMA,
        "inspected_seconds": inspected,
        "source_duration_seconds": raw,
        "partial_segment": partial,
        "palette_name": "sampled first segment" if partial else "sampled video palette",
        "frames": frames,
        "frame_count": len(frames),
        "note": "Point samples with timestamps; not a percentage of footage watched.",
    }


def carousel_selection(child_count: int) -> dict:
    n = int(child_count or 0)
    keep = LIMITS["carousel_children_max"]
    if n <= 0:
        return {"selected_indices": [], "omitted_indices": [], "known_children": 0}
    if n <= keep:
        return {"selected_indices": list(range(n)), "omitted_indices": [], "known_children": n}
    chosen = []
    for i in range(keep):
        idx = int(round(i * (n - 1) / (keep - 1)))
        if idx not in chosen:
            chosen.append(idx)
    omitted = [i for i in range(n) if i not in chosen]
    return {"selected_indices": chosen, "omitted_indices": omitted, "known_children": n}


def _rgb_to_hsv(r, g, b):
    mx = max(r, g, b)
    mn = min(r, g, b)
    d = mx - mn
    s = 0.0 if mx == 0 else d / mx
    if d == 0:
        h = 0.0
    elif mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h = (h / 6.0) % 1.0
    return h, s, mx


def compute_visual_descriptors(pixels: list[tuple[float, float, float]], colour_space="srgb") -> dict:
    """pixels are linear-ish 0..1 RGB after documented sRGB conversion by the caller."""
    if not pixels:
        return {
            "version": DESCRIPTOR_VERSION,
            "status": "unknown",
            "reason": "no_pixels",
            "mean_luminance": None,
            "saturation_mean": None,
            "temporal": {"cut_rate": None, "motion": None, "beat_sync": None},
        }
    if colour_space not in ("srgb",):
        return {
            "version": DESCRIPTOR_VERSION,
            "status": "unknown",
            "reason": "unsupported_colour",
            "mean_luminance": None,
            "saturation_mean": None,
            "hue_histogram": None,
        }
    sample = pixels
    if len(pixels) > MAX_SAMPLE_PIXELS:
        rng = random.Random(CLUSTER_SEED)
        sample = rng.sample(pixels, MAX_SAMPLE_PIXELS)
    lums = []
    sats = []
    hues = []
    achromatic = 0
    for r, g, b in sample:
        y = 0.2126 * r + 0.7152 * g + 0.0722 * b
        h, s, _v = _rgb_to_hsv(r, g, b)
        lums.append(y)
        sats.append(s)
        if s < LOW_SATURATION:
            achromatic += 1
        else:
            hues.append(h)
    mean_l = sum(lums) / len(lums)
    var = sum((y - mean_l) ** 2 for y in lums) / len(lums)
    hist = [0] * HUE_SECTORS
    for h in hues:
        hist[min(HUE_SECTORS - 1, int(h * HUE_SECTORS))] += 1
    hue_frac = [c / len(hues) for c in hist] if hues else [None] * HUE_SECTORS
    centroids = _palette_centroids(sample, PALETTE_CENTROIDS)
    return {
        "version": DESCRIPTOR_VERSION,
        "status": "ready",
        "colour_space": "srgb",
        "seed": CLUSTER_SEED,
        "sample_count": len(sample),
        "low_saturation_threshold": LOW_SATURATION,
        "mean_luminance": mean_l,
        "luminance_dispersion": math.sqrt(var),
        "saturation_mean": sum(sats) / len(sats),
        "achromatic_fraction": achromatic / len(sample),
        "hue_histogram": hue_frac,
        "palette_centroids": centroids,
        "palette_scope": "uniform_frames_only",
        "temporal": {"cut_rate": None, "motion": None, "beat_sync": None, "reason": "detector_unqualified"},
    }


def uniform_palette(frame_descriptors: list[dict]) -> dict:
    """Only palette_uniform frames contribute. Opening-only frames are ignored."""
    chosen = [d for d in frame_descriptors if "palette_uniform" in (d.get("roles") or []) and d.get("mean_luminance") is not None]
    if not chosen:
        return {"status": "unknown", "reason": "no_uniform_frames", "mean_luminance": None, "saturation_mean": None}
    return {
        "status": "ready",
        "mean_luminance": sum(d["mean_luminance"] for d in chosen) / len(chosen),
        "saturation_mean": sum(d["saturation_mean"] for d in chosen) / len(chosen),
        "frame_count": len(chosen),
        "version": DESCRIPTOR_VERSION,
    }


def _palette_centroids(pixels, k):
    if len(pixels) < k:
        return [list(p) for p in pixels]
    rng = random.Random(CLUSTER_SEED)
    cents = [list(p) for p in rng.sample(pixels, k)]
    for _ in range(8):
        buckets = [[] for _ in range(k)]
        for p in pixels:
            idx = min(range(k), key=lambda i: _dist(p, cents[i]))
            buckets[idx].append(p)
        for i, bucket in enumerate(buckets):
            if not bucket:
                continue
            cents[i] = [sum(x[c] for x in bucket) / len(bucket) for c in range(3)]
    return cents


def _dist(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(3))


def reject_oversize_frame(width: int, height: int) -> str | None:
    if width * height > LIMITS["decode_max_pixels"]:
        return "oversize_frame"
    return None
