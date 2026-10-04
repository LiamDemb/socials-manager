"""Cross-format adaptation bridges (versioned)."""
TRANSFER_REGISTRY_VERSION = "transfer-v1"

BRIDGES = {
    ("carousel", "video"): {
        "element": "announcement_sequence",
        "limitation": "Platform response and timing evidence do not transfer.",
    },
    ("image", "video"): {
        "element": "visual_treatment",
        "limitation": "Motion and audio claims are not established.",
    },
    ("video", "story"): {
        "element": "performance_clip_concept",
        "limitation": "Story cadence and private metrics differ.",
    },
}


def find_bridge(source_fmt: str, target_fmt: str) -> dict | None:
    s = (source_fmt or "").lower()
    t = (target_fmt or "").lower()
    for (a, b), meta in BRIDGES.items():
        if a in s and b in t:
            return meta
    return None
