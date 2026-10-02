"""Server-side validation independent of model output."""
import re
import uuid

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I),
    re.compile(r"system\s*:", re.I),
    re.compile(r"<\s*script", re.I),
]


def sanitize_retrieved_text(text: str, limit: int = 4000) -> str:
    cleaned = (text or "")[:limit]
    for pat in _INJECTION_PATTERNS:
        cleaned = pat.sub("[filtered]", cleaned)
    return cleaned


def resolve_evidence_ids(bundle: dict) -> set[str]:
    ids = set()
    for ref in bundle.get("observation_refs") or []:
        if isinstance(ref, dict):
            for key in ("observation_version_id", "observation_id"):
                if ref.get(key):
                    ids.add(str(ref[key]))
    for ref in bundle.get("finding_refs") or []:
        if ref.get("finding_id"):
            ids.add(str(ref["finding_id"]))
    return ids


def validate_citations(cited_ids: list, bundle: dict) -> list[str]:
    allowed = resolve_evidence_ids(bundle)
    errors = []
    for cid in cited_ids or []:
        if not cid:
            errors.append("empty_citation")
            continue
        try:
            uuid.UUID(str(cid))
        except ValueError:
            if cid not in allowed:
                errors.append(f"unknown_citation:{cid}")
    return errors


def validate_activity_draft(item: dict, bundle: dict) -> list[str]:
    errors = []
    kind = item.get("kind") or ""
    if kind == "evidence_backed" and not bundle.get("observation_refs") and not bundle.get("finding_refs"):
        errors.append("no_evidence_for_backed_tactic")
    cited = item.get("evidence_ids") or []
    errors.extend(validate_citations(cited, bundle))
    if item.get("channel") == "email" and not item.get("email_list_confirmed"):
        errors.append("email_without_list")
    return errors
