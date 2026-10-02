"""Versioned feature and analysis spec registry (configuration, not learned semantics)."""
REGISTRY_VERSION = "registry-v1"

FEATURES = {
    "verified_format": {"version": "1", "review_required": True},
    "reviewed_purpose": {"version": "1", "review_required": True},
    "reviewed_narrative": {"version": "1", "review_required": True},
    "release_phase": {"version": "1", "review_required": True},
    "broad_time_window": {"version": "1", "review_required": False},
    "paid_organic_unknown": {"version": "1", "review_required": True},
    "interval_activity_count": {"version": "1", "review_required": False},
}

MODEL_FAMILIES = {
    "post_response": {"version": "1", "implementation": "intelligence.stats.post_response"},
    "interval_response": {"version": "1", "implementation": "intelligence.stats.interval_response"},
    "temporal_window": {"version": "1", "implementation": "intelligence.stats.temporal_window"},
}

# runnable=True means an executable runner exists; qualification is separate
ANALYSIS_SPECS = [
    {
        "key": "post_public_response_v1",
        "family": "post_response",
        "version": "1",
        "target_metric_id": "",
        "runnable": True,
        "config": {
            "measurement_age_days": 7,
            "features": ["verified_format", "reviewed_purpose"],
            "min_independent_units": 4,
            "qualification_domain": "post_content_low_dim",
        },
    },
    {
        "key": "interval_cadence_v1",
        "family": "interval_response",
        "version": "1",
        "target_metric_id": "",
        "runnable": True,
        "config": {
            "lags": [1, 7],
            "trend_control": True,
            "phase_control": True,
            "min_periods": 8,
            "qualification_domain": "interval_cadence",
        },
    },
    {
        "key": "temporal_broad_window_v1",
        "family": "temporal_window",
        "version": "1",
        "target_metric_id": "",
        "runnable": True,
        "config": {
            "requires_timezone": True,
            "min_posts": 6,
            "qualification_domain": "temporal_window",
        },
    },
    {
        "key": "trial_response_v1",
        "family": "trial_response",
        "version": "1",
        "runnable": False,
        "config": {"note": "No denominator contract yet"},
    },
]


def sync_analysis_specs():
    from core import clock

    from .models import AnalysisSpec

    for spec in ANALYSIS_SPECS:
        AnalysisSpec.objects.update_or_create(
            key=spec["key"],
            defaults={
                "family": spec["family"],
                "version": spec["version"],
                "target_metric_id": spec.get("target_metric_id") or "",
                "config": spec.get("config") or {},
                "runnable": spec.get("runnable", False),
                "created_at": clock.now(),
            },
        )
