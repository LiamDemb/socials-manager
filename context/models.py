import uuid

from django.db import models


class PeerCandidate(models.Model):
    """Discovery signal (e.g. Last.fm similar). Not a peer until owner review."""
    SOURCES = [(s, s) for s in ["lastfm", "manual", "reference_artist"]]
    STATES = [(s, s) for s in ["pending", "approved", "rejected"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=20, choices=SOURCES)
    name = models.CharField(max_length=200)
    lastfm_url = models.URLField(blank=True, default="")
    lastfm_mbid = models.CharField(max_length=36, blank=True, default="")
    match_score = models.FloatField(null=True)
    musicbrainz_mbid = models.CharField(max_length=36, blank=True, default="")
    review_state = models.CharField(max_length=12, choices=STATES, default="pending")
    notes = models.TextField(blank=True, default="")
    provenance = models.JSONField(default=dict)
    created_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "name"], name="unique_candidate_name_per_source")]


class PeerProfile(models.Model):
    STATES = [(s, s) for s in ["pending", "reviewed", "rejected"]]
    ROLES = [(s, s) for s in ["comparable", "aspirational", "reference_only", "excluded"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    handle = models.CharField(max_length=80, blank=True, default="")
    label = models.CharField(max_length=200)
    instagram_username = models.CharField(max_length=80, blank=True, default="")
    musicbrainz_artist_id = models.CharField(max_length=36, blank=True, default="")
    lastfm_name = models.CharField(max_length=200, blank=True, default="")
    review_state = models.CharField(max_length=12, choices=STATES, default="pending")
    peer_role = models.CharField(max_length=20, choices=ROLES, default="comparable")
    notes = models.TextField(blank=True, default="")
    capability = models.JSONField(default=dict)
    collection_health = models.JSONField(default=dict)
    created_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True)
    candidate = models.ForeignKey(PeerCandidate, null=True, blank=True, on_delete=models.SET_NULL)


class PeerCollectionEntry(models.Model):
    STATES = [(s, s) for s in ["queued", "collecting", "ok", "failed", "unavailable", "blocked"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    peer = models.ForeignKey(PeerProfile, on_delete=models.CASCADE, related_name="collection_entries")
    state = models.CharField(max_length=12, choices=STATES, default="queued")
    cursor = models.JSONField(default=dict)
    last_snapshot = models.JSONField(default=dict)
    last_error = models.CharField(max_length=300, blank=True, default="")
    attempts = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField()
    created_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["peer"], name="one_collection_entry_per_peer")]


class InspirationReference(models.Model):
    SCOPES = [(s, s) for s in ["global", "campaign", "object"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(max_length=12, choices=SCOPES, default="global")
    scope_ref = models.CharField(max_length=64, blank=True, default="")
    title = models.CharField(max_length=200)
    url = models.URLField(max_length=500, blank=True, default="")
    published_at = models.DateField(null=True)
    retrieved_at = models.DateTimeField()
    excerpt = models.TextField(blank=True, default="")
    influence = models.TextField(blank=True, default="")
    in_analytical_pool = models.BooleanField(default=False)
    collection_source = models.CharField(max_length=40, blank=True, default="manual")


class PeerMedia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    peer = models.ForeignKey(PeerProfile, on_delete=models.CASCADE, related_name="media")
    external_id = models.CharField(max_length=80)
    permalink = models.URLField(max_length=500, blank=True, default="")
    caption = models.TextField(blank=True, default="")
    media_type = models.CharField(max_length=40, blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)
    snapshot = models.JSONField(default=dict)
    collected_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["peer", "external_id"], name="unique_peer_media")]
        ordering = ["-published_at"]


class ReviewedContextItem(models.Model):
    MEANING = [(s, s) for s in ["unknown", "confirmed", "corrected", "rejected"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_label = models.CharField(max_length=200)
    raw_text = models.TextField()
    meaning_state = models.CharField(max_length=12, choices=MEANING, default="unknown")
    reviewed_at = models.DateTimeField(null=True)
    notes = models.TextField(blank=True, default="")
