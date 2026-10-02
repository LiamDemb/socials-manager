"""Claim validation beyond citation IDs."""
CLAIM_MEASURED = "measured"
CLAIM_ASSOCIATION = "association"
CLAIM_TRANSFER = "transfer"
CLAIM_STRATEGIC = "strategic"
CLAIM_CREATIVE = "creative"


def validate_claim(claim: dict, evidence_index: dict) -> list[str]:
    errors = []
    kind = claim.get("kind")
    ref = claim.get("evidence_ref")
    if kind in (CLAIM_MEASURED, CLAIM_ASSOCIATION) and ref:
        ev = evidence_index.get(ref)
        if not ev:
            errors.append("unknown_evidence_ref")
            return errors
        if claim.get("metric_id") and ev.get("metric_id") != claim.get("metric_id"):
            errors.append("metric_mismatch")
        if claim.get("value") is not None and ev.get("value") is not None:
            try:
                if float(claim["value"]) != float(ev["value"]):
                    errors.append("numeric_mismatch")
            except (TypeError, ValueError):
                errors.append("invalid_numeric_claim")
    if kind == CLAIM_CREATIVE and claim.get("presents_as_measured"):
        errors.append("creative_cannot_present_as_measured")
    return errors


def build_claim_records(strategic, evidence_support, transfer_note: str = "") -> list[dict]:
    claims = []
    if evidence_support.get("proposition"):
        claims.append(
            {
                "kind": CLAIM_ASSOCIATION if evidence_support.get("support_label") == "transfer_hypothesis" else CLAIM_MEASURED,
                "text": evidence_support["proposition"],
                "evidence_ref": evidence_support.get("primary_ref"),
            }
        )
    if transfer_note or evidence_support.get("transfer_limits"):
        claims.append({"kind": CLAIM_TRANSFER, "text": transfer_note or evidence_support.get("transfer_limits")})
    if strategic.get("rationale"):
        claims.append({"kind": CLAIM_STRATEGIC, "text": strategic["rationale"]})
    return claims
