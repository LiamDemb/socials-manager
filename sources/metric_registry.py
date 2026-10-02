"""Versioned metric definitions. Existing versions are immutable; a semantic change adds a new version."""

S4A = "spotify_for_artists"

DEFINITIONS = [
    dict(id="spotify.recording.streams.v1", provider=S4A, code="recording.streams", version=1, label="Song streams",
         grain="utc_day", kind="flow", scope_kind="recording", csv_column="streams", outcome_modes=["total"],
         definition="Daily streams of one recording, Spotify UTC day. Sum within the recording and date range."),
    dict(id="spotify.artist.streams.v1", provider=S4A, code="artist.streams", version=1, label="Artist streams",
         grain="utc_day", kind="flow", scope_kind="artist", csv_column="streams", outcome_modes=["total"],
         definition="Daily streams across the artist catalogue, Spotify UTC day. Never add to song streams."),
    dict(id="spotify.artist.listeners.v1", provider=S4A, code="artist.listeners", version=1, label="Daily listeners",
         grain="utc_day", kind="daily_unique", scope_kind="artist", csv_column="listeners", outcome_modes=[],
         definition="Unique listeners on one UTC day. A sum across days is not a count of people."),
    dict(id="spotify.artist.monthly_listeners.v1", provider=S4A, code="artist.monthly_listeners", version=1, label="Monthly listeners",
         grain="utc_day", kind="rolling_stock", scope_kind="artist", csv_column="monthly listeners", outcome_modes=["level", "gain"],
         definition="Rolling 28-day listeners as of the day. Use the latest value; never sum snapshots."),
    dict(id="spotify.artist.monthly_active_listeners.v1", provider=S4A, code="artist.monthly_active_listeners", version=1,
         label="Monthly active listeners", grain="utc_day", kind="nested_stock", scope_kind="artist", csv_column="monthly active listeners",
         outcome_modes=["level"], parent_id="spotify.artist.monthly_listeners.v1",
         definition="Rolling 28-day subset of monthly listeners. Not additive with monthly listeners."),
    dict(id="spotify.artist.super_listeners.v1", provider=S4A, code="artist.super_listeners", version=1, label="Super listeners",
         grain="utc_day", kind="nested_stock", scope_kind="artist", csv_column="super listeners", outcome_modes=["level"],
         parent_id="spotify.artist.monthly_active_listeners.v1",
         definition="Rolling 28-day subset of active listeners. Not additive with its parent segments."),
    dict(id="spotify.artist.playlist_adds.v1", provider=S4A, code="artist.playlist_adds", version=1, label="Playlist adds",
         grain="utc_day", kind="flow", scope_kind="artist", csv_column="playlist adds", outcome_modes=["total"],
         definition="Daily playlist adds across the artist catalogue, UTC day."),
    dict(id="spotify.artist.saves.v1", provider=S4A, code="artist.saves", version=1, label="Artist saves",
         grain="utc_day", kind="flow", scope_kind="artist", csv_column="saves", outcome_modes=["total"],
         definition="Daily saves across the artist catalogue, UTC day. Not song saves and not pre-saves."),
    dict(id="spotify.artist.followers.v1", provider=S4A, code="artist.followers", version=1, label="Spotify followers",
         grain="utc_day", kind="stock", scope_kind="artist", csv_column="followers", outcome_modes=["gain", "level"],
         definition="Total followers as of the UTC day. Gain is latest minus a compatible baseline."),
    # Outcome contracts that need a source not yet connected. They yield "Needs source", never zero.
    dict(id="instagram.account.followers.v1", provider="instagram", code="account.followers", version=1, label="Instagram followers",
         grain="snapshot", kind="stock", scope_kind="artist", outcome_modes=["gain", "level"],
         definition="Own professional account follower total at collection time. Needs an authorised Instagram source (Stage 2)."),
    dict(id="presave.release.confirmed.v1", provider="presave_provider", code="release.confirmed_presaves", version=1,
         label="Confirmed pre-saves", grain="snapshot", kind="cumulative", scope_kind="recording", outcome_modes=["level"],
         definition="Provider-confirmed pre-saves for one identified release. Clicks, saves and playlist adds are different metrics."),
    dict(id="tickets.event.net.v1", provider="ticket_provider", code="event.net_tickets", version=1, label="Net tickets",
         grain="snapshot", kind="cumulative", scope_kind="event", outcome_modes=["level"],
         definition="Paid plus issued tickets minus refunds and cancellations for one event. Latest cumulative snapshot; never sum snapshots."),
]

AUDIENCE_HEADER = ["date", "listeners", "monthly listeners", "monthly active listeners", "super listeners",
                   "streams", "playlist adds", "saves", "followers"]
RECORDING_HEADER = ["date", "streams"]


def sync_definitions(MetricDefinition):
    """Insert missing definitions. Never mutates an existing version."""
    created = 0
    for spec in DEFINITIONS:
        if MetricDefinition.objects.filter(pk=spec["id"]).exists():
            continue
        spec = dict(spec)
        parent = spec.pop("parent_id", None)
        MetricDefinition.objects.create(parent_id=parent, **spec)
        created += 1
    return created


def column_metric_ids(scope):
    if scope == "artist":
        by_col = {d["csv_column"]: d["id"] for d in DEFINITIONS if d["provider"] == S4A and d["scope_kind"] == "artist"}
        return [(c, by_col[c]) for c in AUDIENCE_HEADER[1:]]
    return [("streams", "spotify.recording.streams.v1")]
