"""Extensible campaign type registry. Fields are conditional on type; no single form holds every field."""

TYPES = {
    "single": {"label": "Single release", "object_kinds": ["recording"], "anchor": "Release date", "group": "release"},
    "ep_album": {"label": "EP or album", "object_kinds": ["release"], "anchor": "Release date", "group": "release"},
    "live_show": {"label": "Live show", "object_kinds": ["event"], "anchor": "Show date", "group": "show"},
    "tour_announcement": {"label": "Tour announcement", "object_kinds": ["event"], "anchor": "Announcement date", "group": "show"},
    "music_video": {"label": "Music video", "object_kinds": ["video"], "anchor": "Premiere date", "group": "release"},
    "merch_launch": {"label": "Merch launch", "object_kinds": ["merch"], "anchor": "Launch date", "group": "release"},
    "audience_growth": {"label": "Audience growth", "object_kinds": [], "anchor": None, "group": "growth"},
    "content_push": {"label": "Content push", "object_kinds": [], "anchor": None, "group": "growth"},
    "other": {"label": "Other", "object_kinds": [], "anchor": None, "group": "growth"},
}

CHANNELS = [
    ("instagram", "Instagram", ["Reel", "Feed post", "Carousel", "Story"]),
    ("facebook", "Facebook", ["Post", "Reel", "Event"]),
    ("youtube", "YouTube", ["Video", "Short"]),
    ("spotify", "Spotify", ["Pitch", "Profile update", "Pre-save link"]),
    ("email", "Email", ["Newsletter"]),
    ("outreach", "Outreach", ["Venue", "Press", "Playlist curator"]),
    ("internal", "Internal", ["Task", "Review"]),
]
CHANNEL_LABELS = {c: label for c, label, _ in CHANNELS}
FORMATS = {c: formats for c, _, formats in CHANNELS}

TEMPLATE_VERSION = "operational-templates-v1"


def type_label(key):
    return TYPES.get(key, {}).get("label", key)
