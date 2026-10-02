"""Versioned tactic catalogue. Ranking is deterministic; LLM only narrates selected tactics."""

from .contracts import campaign_group

TACTIC_CATALOGUE_VERSION = "tactics-v3"


def tactic_observable_metrics(tactic: dict) -> list[str]:
    return list(tactic.get("observable_metrics") or tactic.get("outcome_metrics") or [])


def _t(
    id,
    purposes,
    phases,
    channels,
    formats,
    roles,
    observable_metrics,
    hypothesis,
    transfer_limits,
    effort_minutes=45,
    requires_assets=True,
    requires_email_list=False,
    kind=None,
    pairs_with=None,
    purposes_notes="",
):
    entry = {
        "id": id,
        "purposes": purposes,
        "phases": phases,
        "channels": channels,
        "formats": formats,
        "roles": roles,
        "observable_metrics": observable_metrics,
        "outcome_metrics": observable_metrics,
        "contribution": {
            "supports_primary": True,
            "hypothesis": hypothesis,
        },
        "context_suitability": purposes_notes,
        "transfer_limits": transfer_limits,
        "effort_minutes": effort_minutes,
        "requires_assets": requires_assets,
        "pairs_with": pairs_with or [],
    }
    if requires_email_list:
        entry["requires_email_list"] = True
    if kind:
        entry["kind"] = kind
    return entry


TACTICS = [
    _t(
        "ig_reel_teaser",
        ["release", "growth"],
        ["pre_release", "launch", "sustain"],
        ["instagram"],
        ["Reel"],
        ["discovery", "engagement"],
        ["instagram.account.followers.v1", "spotify.recording.streams.v1"],
        "Short-form video can surface the artist or release to people who do not follow yet; reach is not streams.",
        "Observed reach or engagement is not proof of streams, saves, or follower gain.",
        pairs_with=["ig_story_teaser"],
    ),
    _t(
        "ig_story_teaser",
        ["release", "show", "growth"],
        ["pre_release", "launch", "sustain", "show_week"],
        ["instagram"],
        ["Story"],
        ["engagement", "conversion"],
        ["instagram.account.followers.v1"],
        "Stories can remind an existing audience, reinforce anticipation, or point to a link or moment; not a discovery engine on their own.",
        "Story views are not comparable to feed reach at the same age and do not measure follower acquisition.",
        effort_minutes=25,
        pairs_with=["ig_reel_teaser"],
    ),
    _t(
        "ig_carousel",
        ["release", "show"],
        ["pre_release", "launch", "show_week"],
        ["instagram"],
        ["Carousel"],
        ["engagement", "conversion"],
        ["instagram.account.followers.v1"],
        "Carousels can explain context (credits, dates, behind-the-scenes) to people already considering the release or show.",
        "Engagement patterns may not transfer across formats or to ticket sales.",
        effort_minutes=50,
    ),
    _t(
        "fb_post",
        ["release", "show", "growth"],
        ["pre_release", "launch", "sustain", "show_week"],
        ["facebook"],
        ["Post"],
        ["engagement", "discovery"],
        ["instagram.account.followers.v1"],
        "Facebook posts can reach page followers and cross-post audiences where the Page is active.",
        "Facebook engagement does not measure Spotify or Instagram follower outcomes.",
    ),
    _t(
        "yt_short_teaser",
        ["release", "growth"],
        ["pre_release", "launch", "sustain"],
        ["youtube"],
        ["Short"],
        ["discovery", "engagement"],
        ["spotify.recording.streams.v1"],
        "Shorts can introduce audio or visuals to YouTube viewers; views are not streams.",
        "Views are not streams or saves.",
    ),
    _t(
        "email_list_update",
        ["release", "show", "growth"],
        ["launch", "show_week"],
        ["email"],
        ["Email"],
        ["conversion", "retention"],
        ["instagram.account.followers.v1"],
        "Email reaches people who already opted in; useful for announcements and direct links.",
        "Requires confirmed opted-in list; does not measure social follower growth from the send alone.",
        requires_email_list=True,
        effort_minutes=35,
    ),
    _t(
        "spotify_pitch_followup",
        ["release"],
        ["launch", "sustain"],
        ["spotify", "internal"],
        ["Pitch", "Task"],
        ["measurement", "conversion"],
        ["spotify.recording.streams.v1"],
        "Operational follow-up on pitching and playlist context; not an observed post effect.",
        "Manual operational follow-up; not an observed tactic effect.",
        kind="operational",
        requires_assets=False,
        effort_minutes=30,
    ),
]


def candidate_tactics(campaign_type, phase, channels, context: dict | None = None):
    """Hard exclusions only: purpose, phase, channel, prerequisites."""
    context = context or {}
    group = campaign_group(campaign_type)
    channels = set(channels or [])
    assets_ready = context.get("assets_ready_date")
    start = context.get("start_date")
    email_ok = context.get("email_list_confirmed")
    rejected = []
    out = []
    for t in TACTICS:
        if group not in t["purposes"]:
            rejected.append((t["id"], "purpose_mismatch"))
            continue
        if phase and phase not in t["phases"]:
            rejected.append((t["id"], "phase_mismatch"))
            continue
        if channels and not channels.intersection(t["channels"]):
            rejected.append((t["id"], "channel_unselected"))
            continue
        if t.get("requires_email_list") and not email_ok:
            rejected.append((t["id"], "email_list_missing"))
            continue
        if t.get("requires_assets") and assets_ready and start and assets_ready > start:
            rejected.append((t["id"], "assets_after_window_start"))
            continue
        out.append(t)
    return sorted(out, key=lambda x: x["id"]), rejected


def eligible_tactics(campaign_type, phase, channels, metric_ids=None, context: dict | None = None):
    """Backward-compatible alias; metric_ids are ignored for selection (ADR 0004)."""
    return candidate_tactics(campaign_type, phase, channels, context)
