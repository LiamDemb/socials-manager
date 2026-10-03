"""Honest display labels for provider media types (no Reel unless known)."""

IG_TYPE_LABELS = {
    "IMAGE": "Image",
    "VIDEO": "Video",
    "CAROUSEL_ALBUM": "Carousel",
    "REELS": "Reel",
    "REEL": "Reel",
}


def display_media_type(raw: str) -> str:
    if not raw:
        return "Post"
    key = raw.strip().upper().replace(" ", "_")
    return IG_TYPE_LABELS.get(key, raw.replace("_", " ").title())


def channel_for_media_type(raw: str) -> str:
    return "instagram"
