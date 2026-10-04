"""Poisson log-link fit for content specs. One posterior answers later contrasts."""
import math


def _as_float(value):
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def design_matrix(rows: list[dict], feature_names: list[str]) -> tuple[list[float], list[list[float]], list[str]]:
    """One row per canonical post. Missing feature values are dropped, not treated as zero."""
    ys = []
    xs = []
    ids = []
    seen = set()
    for row in rows:
        pid = str(row.get("peer_media_id") or row.get("id") or len(seen))
        if pid in seen:
            continue
        seen.add(pid)
        response = row.get("response")
        if response is None:
            continue
        vec = []
        for name in feature_names:
            number = _as_float((row.get("features") or {}).get(name))
            if number is None:
                vec = []
                break
            vec.append(number)
        if not vec:
            continue
        ys.append(float(response))
        xs.append(vec)
        ids.append(pid)
    return ys, xs, ids


def _diagnostics(idata) -> dict:
    import arviz as az

    summary = az.summary(idata, var_names=["beta"])
    diverging = None
    if "diverging" in getattr(idata, "sample_stats", {}):
        diverging = int(idata.sample_stats["diverging"].values.sum())
    return {
        "rhat_max": float(summary["r_hat"].max()),
        "ess_bulk_min": float(summary["ess_bulk"].min()),
        "divergences": diverging,
        "support": "exploratory",
        "note": "Synthetic or unreviewed rows prove the sampler path. They do not qualify an owner-data finding.",
    }


def fit_poisson(rows: list[dict], feature_names: list[str], *, draws: int = 200, tune: int = 200, seed: int = 1) -> dict:
    ys, xs, ids = design_matrix(rows, feature_names)
    if len(ys) < 8:
        return {
            "status": "insufficient_data",
            "detail": f"Need at least 8 complete posts for a mechanics fit; have {len(ys)}.",
            "sample_size": len(ys),
            "sampler_invoked": False,
        }
    for col, name in enumerate(feature_names):
        values = {row[col] for row in xs}
        if len(values) < 2:
            return {
                "status": "blocked",
                "blocker_code": "no_feature_variation",
                "detail": f"{name} does not vary in the admitted rows.",
                "sampler_invoked": False,
            }
    try:
        import numpy as np
        import pymc as pm
    except Exception as exc:
        return {
            "status": "blocked",
            "blocker_code": "dependency_unavailable",
            "detail": f"{type(exc).__name__}: {exc}",
            "sampler_invoked": False,
        }
    y = np.asarray(ys, dtype=float)
    x = np.asarray(xs, dtype=float)
    try:
        with pm.Model():
            alpha = pm.Normal("alpha", 0.0, 1.0)
            beta = pm.Normal("beta", 0.0, 0.5, shape=len(feature_names))
            mu = pm.math.exp(alpha + pm.math.dot(x, beta))
            pm.Poisson("y", mu=mu, observed=np.round(y).astype(int))
            idata = pm.sample(
                draws=draws,
                tune=tune,
                chains=2,
                cores=1,
                progressbar=False,
                random_seed=seed,
                compute_convergence_checks=True,
            )
        flat = idata.posterior["beta"].values.reshape(-1, len(feature_names))
        stored = {name: [float(v) for v in flat[:, i]] for i, name in enumerate(feature_names)}
        alpha = [float(v) for v in idata.posterior["alpha"].values.reshape(-1)]
        diagnostics = _diagnostics(idata)
    except Exception as exc:
        return {
            "status": "blocked",
            "blocker_code": "sampler_failed",
            "detail": f"{type(exc).__name__}: {exc}"[:500],
            "sampler_invoked": True,
        }
    return {
        "status": "exploratory",
        "family": "post_response",
        "likelihood": "poisson_log",
        "features": feature_names,
        "sample_size": len(ys),
        "post_ids": ids,
        "draws": stored,
        "alpha_draws": alpha,
        "diagnostics": diagnostics,
        "sampler_invoked": True,
        "proposition": "Exploratory log public-likes association. Not a causal effect and not owner-data qualified.",
    }


def _poisson_loglik(count: int, mu: float) -> float:
    mu = min(1e6, max(1e-8, mu))
    return count * math.log(mu) - mu - math.lgamma(count + 1)


def evaluate_draws(fit: dict, rows: list[dict]) -> dict:
    """Score stored draws on held-out rows. Does not sample and does not qualify owner data."""
    features = list((fit or {}).get("features") or [])
    draws = (fit or {}).get("draws") or {}
    alpha = list((fit or {}).get("alpha_draws") or [])
    if not features or any(not draws.get(name) for name in features) or not alpha:
        return {
            "status": "blocked",
            "blocker_code": "stale_dependency",
            "detail": "Evaluation needs the stored intercept and coefficient draws from a fit.",
            "sampler_invoked": False,
            "refit": False,
            "qualified_on_owner_data": False,
        }
    ys, xs, ids = design_matrix(rows, features)
    if len(ys) < 4:
        return {
            "status": "insufficient_data",
            "detail": f"Holdout needs at least 4 complete posts; have {len(ys)}.",
            "sample_size": len(ys),
            "sampler_invoked": False,
            "refit": False,
            "qualified_on_owner_data": False,
        }
    n = min(len(alpha), *(len(draws[name]) for name in features))
    step = max(1, n // 40)
    mean_y = max(sum(ys) / len(ys), 1e-6)
    model_scores = []
    baseline_scores = []
    for i in range(0, n, step):
        coefficients = [draws[name][i] for name in features]
        model = 0.0
        baseline = 0.0
        for y, x in zip(ys, xs):
            eta = alpha[i] + sum(coef * value for coef, value in zip(coefficients, x))
            eta = min(20.0, max(-20.0, eta))
            count = int(round(y))
            model += _poisson_loglik(count, math.exp(eta))
            baseline += _poisson_loglik(count, mean_y)
        model_scores.append(model)
        baseline_scores.append(baseline)
    model_mean = sum(model_scores) / len(model_scores)
    baseline_mean = sum(baseline_scores) / len(baseline_scores)
    diagnostics = (fit or {}).get("diagnostics") or {}
    reasons = ["synthetic_or_unreviewed"]
    if diagnostics.get("rhat_max") is None or diagnostics.get("rhat_max", 99) > 1.01:
        reasons.append("rhat")
    if (diagnostics.get("ess_bulk_min") or 0) < 400:
        reasons.append("ess")
    if diagnostics.get("divergences") not in (0,):
        reasons.append("divergences")
    if model_mean <= baseline_mean:
        reasons.append("baseline")
    reasons.append("no_grouped_time_holdout")
    return {
        "status": "exploratory",
        "feature_set": features,
        "holdout_n": len(ys),
        "holdout_ids": ids,
        "posterior_mean_loglik": model_mean,
        "baseline_mean_loglik": baseline_mean,
        "beats_intercept_baseline": model_mean > baseline_mean,
        "draws_scored": len(model_scores),
        "search_budget": {"fitted_features": features, "contrasts_searched_after_fit": 0},
        "qualification_blockers": reasons,
        "qualified_on_owner_data": False,
        "sampler_invoked": False,
        "refit": False,
        "support": "exploratory",
        "detail": "Held-out Poisson log score against an intercept baseline. This does not qualify an owner-data finding.",
    }


def query_draws(fit: dict, feature: str) -> dict:
    """Read one coefficient from an existing posterior. Does not sample."""
    draws = (fit or {}).get("draws") or {}
    samples = draws.get(feature)
    if not samples:
        return {
            "status": "blocked",
            "blocker_code": "stale_dependency",
            "detail": f"No stored draws for {feature}.",
            "sampler_invoked": False,
        }
    ordered = sorted(samples)
    n = len(ordered)

    def pct(p):
        return ordered[min(n - 1, max(0, int(round(p * (n - 1)))))]

    mean = sum(samples) / n
    p10 = pct(0.10)
    p90 = pct(0.90)
    if p10 > 0:
        ell = p10
    elif p90 < 0:
        ell = p90
    else:
        ell = 0.0
    return {
        "status": "exploratory",
        "feature": feature,
        "posterior_mean_log_response_ratio": mean,
        "p10": p10,
        "p90": p90,
        "ell": ell,
        "n_draws": n,
        "sampler_invoked": False,
        "refit": False,
        "support": "exploratory",
        "detail": "Same posterior as the fit. A second contrast does not call the sampler.",
    }
