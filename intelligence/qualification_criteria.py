"""Frozen before qualify_statistics / qualify_llm runs. Do not auto-tune to pass."""

CRITERIA_FROZEN_AT = "2026-10-03"
STATS_CRITERIA = {
    "frozen_at": CRITERIA_FROZEN_AT,
    "synthetic_min_posts": 12,
    "holdout_fraction": 0.25,
    "max_prior_scale_sensitivity_ratio": 2.0,
    "require_diagnostics": True,
}
LLM_CRITERIA = {
    "frozen_at": CRITERIA_FROZEN_AT,
    "min_request_parse_accuracy": 0.8,
    "min_schema_valid_rate": 1.0,
    "fallback_cannot_pass": True,
    "max_latency_seconds": 120,
}
