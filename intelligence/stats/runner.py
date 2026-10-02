"""Dispatch to family runners."""
from intelligence.analysis import (
    STATUS_BLOCKED,
    STATUS_DESCRIPTIVE_ONLY,
    STATUS_EXPLORATORY,
    STATUS_INSUFFICIENT,
    STATUS_READY,
)

from . import interval_response, post_response, temporal_window


def execute_spec(spec, request: dict, ctx: dict) -> dict:
    family = spec.family
    if family == "post_response":
        return post_response.run(spec, request, ctx)
    if family == "interval_response":
        return interval_response.run(spec, request, ctx)
    if family == "temporal_window":
        return temporal_window.run(spec, request, ctx)
    return {"status": STATUS_BLOCKED, "blocker_code": "unknown_family", "detail": family}


def dependency_blocked(exc: Exception) -> dict:
    return {
        "status": STATUS_BLOCKED,
        "blocker_code": "dependency_unavailable",
        "detail": str(exc)[:300],
        "descriptive": None,
    }
