"""Conservative support labels (support-v1). Not model confidence."""
SUPPORT_SUPPORTED = "supported"
SUPPORT_TRANSFER = "transfer_hypothesis"
SUPPORT_OPERATIONAL = "operational"
SUPPORT_CREATIVE = "creative_draft"
NO_EMPIRICAL = "no_empirical_support"

MIN_INDEPENDENT_UNITS = 3

_LABEL_DISPLAY = {
    SUPPORT_SUPPORTED: "Evidence-backed",
    SUPPORT_TRANSFER: "Transfer hypothesis",
    SUPPORT_OPERATIONAL: "Operational",
    SUPPORT_CREATIVE: "Planning hypothesis",
    NO_EMPIRICAL: "Planning hypothesis",
}


def support_label_display(label: str) -> str:
    return _LABEL_DISPLAY.get(label, "Planning hypothesis")


def classify_tactic_support(tactic: dict, finding_refs: list, observation_refs: list, primary_metric_id: str) -> tuple[str, str]:
    """Legacy wrapper; prefer assess_evidence_support."""
    from .assessments import assess_evidence_support

    slice_bundle = {"finding_refs": finding_refs, "observation_refs": observation_refs}
    ctx = {"primary_metric_id": primary_metric_id}
    ev = assess_evidence_support(tactic, ctx, slice_bundle)
    return ev["support_label"], ev["support_reason"]
