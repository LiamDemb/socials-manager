"""Post-level response runner (descriptive + optional fit attempt)."""
import statistics

from intelligence.analysis import STATUS_BLOCKED, STATUS_DESCRIPTIVE_ONLY, STATUS_INSUFFICIENT, STATUS_READY


FIT_FEATURES = {
    "content_subject_purpose_v1": ["reviewed_purpose"],
    "opening_text_association_v1": ["visible_opening_text"],
    "palette_association_v1": ["mean_luminance", "mean_saturation"],
}


def _fit_features(spec, request) -> list[str]:
    if request.get("features"):
        return list(request["features"])
    return list(FIT_FEATURES.get(spec.key, []))


def observation_frame(spec, request: dict, ctx: dict) -> tuple[list[dict], dict]:
    """Canonical rows for a content spec. Synthetic callers may supply rows; owner fits use the peer builder."""
    domain = (spec.config or {}).get("domain")
    supplied = ctx.get("post_rows")
    if request.get("synthetic"):
        rows = list(supplied or [])
        meta = {
            "source": "synthetic_supplied",
            "version": "caller",
            "row_count": len(rows),
            "qualified_on_owner_data": False,
        }
    elif supplied is not None:
        rows = list(supplied)
        meta = {"source": "supplied", "version": "caller", "row_count": len(rows), "qualified_on_owner_data": False}
    else:
        from intelligence.peer_dataset import DATASET_VERSION, build_peer_post_dataset

        built = build_peer_post_dataset(spec.target_metric_id or ctx.get("primary_metric_id"))
        rows = list(built["post_rows"])
        meta = {
            "source": DATASET_VERSION,
            "version": DATASET_VERSION,
            "dataset_hash": built["dataset_hash"],
            "post_count": built["dataset_meta"]["post_count"],
            "excluded_count": len(built["dataset_meta"].get("excluded") or []),
            "qualified_on_owner_data": False,
        }
    if domain == "video":
        rows = [row for row in rows if "video" in str(row.get("format") or "").lower()]
        meta = {**meta, "domain": "video", "row_count": len(rows)}
    else:
        meta = {**meta, "row_count": len(rows)}
    return rows, meta


def run(spec, request: dict, ctx: dict) -> dict:
    rows = ctx.get("post_rows") or []
    cfg = spec.config or {}
    if request.get("intent") == "fit":
        from .bayes_fit import fit_poisson

        names = _fit_features(spec, request)
        rows, dataset = observation_frame(spec, request, ctx)
        if not names:
            return {
                "status": STATUS_BLOCKED,
                "blocker_code": "no_admitted_features",
                "detail": f"{spec.key} has no numeric content features configured for a Poisson fit.",
                "sampler_invoked": False,
                "dataset": dataset,
            }
        minimum = cfg.get("min_posts", 50)
        if not request.get("synthetic") and len(rows) < minimum:
            return {
                "status": STATUS_INSUFFICIENT,
                "detail": f"Owner-data fit needs at least {minimum} posts; have {len(rows)}.",
                "sample_size": len(rows),
                "sampler_invoked": False,
                "dataset": dataset,
            }
        outcome = fit_poisson(rows, names, draws=int(request.get("draws") or 200), tune=int(request.get("tune") or 200))
        outcome["spec_key"] = spec.key
        outcome["qualified_on_owner_data"] = False
        outcome["dataset"] = dataset
        return outcome
    if request.get("intent") == "query":
        from .bayes_fit import query_draws

        fit = ctx.get("fitted_draws_result")
        if request.get("fit_run_id") and not fit:
            from intelligence.models import FitRun

            stored = FitRun.objects.filter(pk=request["fit_run_id"]).first()
            fit = stored.result if stored else None
        feature = request.get("contrast") or request.get("feature")
        if not feature:
            return {
                "status": STATUS_BLOCKED,
                "blocker_code": "missing_contrast",
                "detail": "Name the coefficient to read from the stored posterior.",
                "sampler_invoked": False,
            }
        return query_draws(fit or {}, feature)
    if request.get("intent") == "evaluate":
        from .bayes_fit import evaluate_draws

        fit = ctx.get("fitted_draws_result")
        if request.get("fit_run_id") and not fit:
            from intelligence.models import FitRun

            stored = FitRun.objects.filter(pk=request["fit_run_id"]).first()
            fit = stored.result if stored else None
        holdout = ctx.get("holdout_rows")
        if holdout is None:
            return {
                "status": STATUS_BLOCKED,
                "blocker_code": "missing_holdout",
                "detail": "Evaluation needs holdout_rows that were not the fitting rows.",
                "sampler_invoked": False,
                "refit": False,
            }
        return evaluate_draws(fit or {}, list(holdout))
    if request.get("intent") == "content_contrast":
        from .content_association import contrast

        feature = request.get("feature") or (cfg.get("features") or ["reviewed_purpose"])[0]
        return contrast(rows, feature, cfg)
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
