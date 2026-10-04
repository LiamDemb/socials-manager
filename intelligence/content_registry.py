"""Registered content features. Aliases map here; do not duplicate vocabularies."""
CONTENT_FEATURES = {
    "instrument_visible": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": False, "group": "subject"},
    "people_performing": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": False, "group": "subject"},
    "artwork_graphics": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": False, "group": "subject"},
    "studio_setting": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": False, "group": "subject"},
    "addressing_camera": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": False, "group": "subject"},
    "visible_opening_text": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": True, "group": "construction"},
    "visible_question": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": False, "group": "construction"},
    "text_overlay": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": False, "group": "construction"},
    "opening_performance": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": False, "group": "construction"},
    "reviewed_purpose": {"version": "1", "type": "enum", "review_required": True, "stat_eligible": True, "group": "purpose"},
    "teaser": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": True, "group": "purpose"},
    "announcement": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": True, "group": "purpose"},
    "reminder": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": True, "group": "purpose"},
    "community_interaction": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": False, "group": "purpose"},
    "behind_the_scenes": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": False, "group": "purpose"},
    "performance_demonstration": {"version": "1", "type": "boolean", "review_required": True, "stat_eligible": False, "group": "purpose"},
    "cta_direction": {"version": "1", "type": "text", "review_required": True, "stat_eligible": False, "group": "purpose"},
    "mean_luminance": {"version": "1", "type": "float", "review_required": False, "stat_eligible": True, "group": "palette"},
    "mean_saturation": {"version": "1", "type": "float", "review_required": False, "stat_eligible": True, "group": "palette"},
    "paid_status": {"version": "1", "type": "enum", "review_required": True, "stat_eligible": False, "group": "context"},
}

PURPOSE_VALUES = ("teaser", "announcement", "reminder", "community_interaction", "behind_the_scenes", "performance_demonstration")

ADMITTED = {
    "reviewed_purpose": PURPOSE_VALUES,
    "paid_status": ("paid", "organic", "unknown"),
}


def is_unknown(value) -> bool:
    return value is None or value == "unknown"
