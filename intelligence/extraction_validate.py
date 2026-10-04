"""Schema and grounding checks for extraction output (section 7)."""
import re

from intelligence.content_registry import ADMITTED, CONTENT_FEATURES

BANNED_PROSE = re.compile(
    r"performed well|engagement rate|went viral|high production quality|conversion",
    re.I,
)


def validate_extraction(outcome: dict, known_asset_ids: set[str] | None = None) -> dict:
    known_asset_ids = known_asset_ids or set()
    accepted = []
    rejected = []
    description = str((outcome.get("output") or {}).get("description") or outcome.get("description") or "")
    if BANNED_PROSE.search(description):
        description = ""
        rejected.append({"reason": "unsupported_prose", "field": "description"})
    for field in outcome.get("fields") or []:
        key = field.get("feature_key")
        if key not in CONTENT_FEATURES:
            rejected.append({"feature_key": key, "reason": "unregistered_field"})
            continue
        value = field.get("value")
        if key in ADMITTED and value not in ADMITTED[key] and value is not None:
            rejected.append({"feature_key": key, "reason": "unadmitted_value"})
            continue
        support = field.get("support") or []
        if value not in (None, "unknown") and not support:
            rejected.append({"feature_key": key, "reason": "missing_support"})
            continue
        bad_asset = False
        for loc in support:
            asset_id = loc.get("asset_id")
            if asset_id and known_asset_ids and asset_id not in known_asset_ids:
                bad_asset = True
            if "time_seconds" in loc and loc["time_seconds"] is not None and loc["time_seconds"] < 0:
                bad_asset = True
        if bad_asset:
            rejected.append({"feature_key": key, "reason": "invalid_support_location"})
            continue
        if "like_count" in field or "comments_count" in field or "popularity" in field:
            rejected.append({"feature_key": key, "reason": "popularity_in_extraction"})
            continue
        accepted.append(field)
    return {"fields": accepted, "rejected": rejected, "description": description}
