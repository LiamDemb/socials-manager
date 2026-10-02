"""Reference baselines for a daily-flow trajectory: the sum over the next `horizon` days."""
from datetime import timedelta

MODELS = {
    "recent_mean_7": "Mean of the last 7 observed days, times the horizon",
    "seasonal_naive_7": "Repeat the last 7 observed days",
}


def predict(model_ref, history, horizon):
    """history: sorted [(date, value)] strictly before the origin."""
    if model_ref not in MODELS:
        raise ValueError(f"Unknown baseline {model_ref}")
    if not history:
        return 0
    last_day = history[-1][0]
    window = [v for d, v in history if d > last_day - timedelta(days=7)]
    if model_ref == "recent_mean_7":
        return round(sum(window) / len(window) * horizon)
    by_day = {d: v for d, v in history}
    total = 0
    for i in range(horizon):
        source_day = last_day - timedelta(days=6) + timedelta(days=i % 7)
        total += by_day.get(source_day, 0)
    return total


def score(rows):
    """MAE and bias in counts. No percentage error: zeros make it undefined."""
    if not rows:
        return {"n": 0, "mae": None, "bias": None, "rows": []}
    errors = [r["predicted"] - r["actual"] for r in rows]
    return {"n": len(rows), "mae": sum(abs(e) for e in errors) / len(errors), "bias": sum(errors) / len(errors), "rows": rows}
