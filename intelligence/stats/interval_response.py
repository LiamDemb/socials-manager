"""Interval cadence runner with declared lags and missingness."""
from intelligence.analysis import STATUS_BLOCKED, STATUS_DESCRIPTIVE_ONLY, STATUS_INSUFFICIENT, STATUS_READY


def run(spec, request: dict, ctx: dict) -> dict:
    periods = ctx.get("interval_rows") or []
    cfg = spec.config or {}
    min_periods = cfg.get("min_periods", 8)
    lags = cfg.get("lags") or [1, 7]
    complete = [p for p in periods if p.get("complete")]
    if len(complete) < 2:
        return {
            "status": STATUS_INSUFFICIENT,
            "detail": "Incomplete interval coverage",
            "lags": lags,
            "sample_size": len(complete),
        }
    activity_totals = [p.get("activity_count") for p in complete if p.get("activity_count") is not None]
    outcomes = [p.get("outcome") for p in complete if p.get("outcome") is not None]
    descriptive = {
        "periods": len(complete),
        "mean_activity": sum(activity_totals) / len(activity_totals) if activity_totals else None,
        "mean_outcome": sum(outcomes) / len(outcomes) if outcomes else None,
        "lags_declared": lags,
        "trend_control": cfg.get("trend_control"),
        "phase_control": cfg.get("phase_control"),
        "temporal_dependence": "not_modelled_in_descriptive_path",
    }
    if len(complete) < min_periods:
        return {
            "status": STATUS_DESCRIPTIVE_ONLY,
            "descriptive": descriptive,
            "detail": f"Below min_periods {min_periods}",
        }
    try:
        import pymc  # noqa: F401
    except ImportError:
        return {
            "status": STATUS_BLOCKED,
            "blocker_code": "dependency_unavailable",
            "detail": "pymc not installed",
            "descriptive": descriptive,
        }
    return {
        "status": STATUS_READY,
        "descriptive": descriptive,
        "proposition": "Observational cadence/outcome association (not causal allocation)",
    }
