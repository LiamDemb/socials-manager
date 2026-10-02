"""Post-level response runner (descriptive + optional fit attempt)."""
import statistics

from intelligence.analysis import STATUS_BLOCKED, STATUS_DESCRIPTIVE_ONLY, STATUS_INSUFFICIENT, STATUS_READY


def run(spec, request: dict, ctx: dict) -> dict:
    rows = ctx.get("post_rows") or []
    cfg = spec.config or {}
    min_units = cfg.get("min_independent_units", 4)
    if len(rows) < 2:
        return {
            "status": STATUS_INSUFFICIENT,
            "detail": f"Need at least 2 posts; have {len(rows)}",
            "sample_size": len(rows),
            "proposition": "Post-level public response summary",
        }
    by_format = {}
    for r in rows:
        fmt = r.get("format") or "unknown"
        by_format.setdefault(fmt, []).append(float(r.get("response") or 0))
    descriptive = {
        k: {"median": statistics.median(v), "n": len(v), "min": min(v), "max": max(v)}
        for k, v in by_format.items()
        if v
    }
    if len(rows) < min_units:
        return {
            "status": STATUS_DESCRIPTIVE_ONLY,
            "descriptive": descriptive,
            "sample_size": len(rows),
            "detail": f"Below qualification minimum ({min_units})",
            "proposition": "Scoped descriptive post response by format",
        }
    try:
        import pymc  # noqa: F401
    except ImportError as e:
        return {
            "status": STATUS_BLOCKED,
            "blocker_code": "dependency_unavailable",
            "detail": "pymc not installed",
            "descriptive": descriptive,
        }
    # Executable path: descriptive qualified enough for ready without claiming Bayesian qualification
    return {
        "status": STATUS_READY,
        "descriptive": descriptive,
        "sample_size": len(rows),
        "proposition": "Format-stratified observed response (not causal)",
        "fit_note": "Sampler available; full posterior qualification via qualify_statistics",
    }
