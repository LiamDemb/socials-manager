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
    ROLES = [(s, s) for s in ["comparable", "aspirational", "reference_only", "excluded", "unresolved"]]
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
    collection_paused = models.BooleanField(default=False)
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
    canonical_key = models.CharField(max_length=120, blank=True, default="")
    is_bookmark = models.BooleanField(default=False)
    ORIGINS = [(s, s) for s in ["manual", "peer_media"]]
    origin_type = models.CharField(max_length=20, choices=ORIGINS, default="manual")
    owner_note = models.TextField(blank=True, default="")
    peer_media = models.ForeignKey(
        "PeerMedia", null=True, blank=True, on_delete=models.SET_NULL, related_name="saved_references"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["peer_media"],
                condition=models.Q(peer_media__isnull=False, is_bookmark=True),
                name="unique_bookmark_per_peer_media",
            ),
        ]


class PeerMedia(models.Model):
    AVAILABILITY = [
        (s, s)
        for s in [
            "link_only",
            "queued",
            "analysing",
            "partial",
            "ready",
            "restricted",
            "failed",
            "evicted",
        ]
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    peer = models.ForeignKey(PeerProfile, on_delete=models.CASCADE, related_name="media")
    provider_namespace = models.CharField(max_length=40, default="instagram")
    acquisition_revision = models.PositiveIntegerField(default=1)
    media_availability = models.CharField(max_length=20, choices=AVAILABILITY, default="link_only")
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


class PeerMediaMetricSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    media = models.ForeignKey(PeerMedia, on_delete=models.CASCADE, related_name="metric_snapshots")
    captured_at = models.DateTimeField()
    metrics = models.JSONField(default=dict)
    source_version = models.CharField(max_length=40, blank=True, default="")

    class Meta:
        ordering = ["-captured_at"]


class MediaAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(PeerMedia, on_delete=models.CASCADE, related_name="assets")
    role = models.CharField(max_length=40)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    relative_path = models.CharField(max_length=300, blank=True, default="")
    mime_type = models.CharField(max_length=80, blank=True, default="")
    byte_size = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(null=True)
    height = models.PositiveIntegerField(null=True)
    duration_seconds = models.FloatField(null=True)
    captured_at = models.DateTimeField()
    retention_class = models.CharField(max_length=40, default="analysis_derivative")

    class Meta:
        indexes = [models.Index(fields=["post", "role"])]


class MediaPack(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(PeerMedia, on_delete=models.CASCADE, related_name="packs")
    profile_version = models.CharField(max_length=40, default="media-compact-v1")
    input_hash = models.CharField(max_length=64)
    manifest_hash = models.CharField(max_length=64, blank=True, default="")
    state = models.CharField(max_length=20, default="pending")
    reason = models.CharField(max_length=120, blank=True, default="")
    sampling_manifest = models.JSONField(default=dict)
    stored_bytes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["post", "profile_version", "input_hash"], name="unique_media_pack_input")
        ]


class ContentAnalysisRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pack = models.ForeignKey(MediaPack, on_delete=models.CASCADE, related_name="analysis_runs")
    adapter = models.CharField(max_length=80)
    model_revision = models.CharField(max_length=120)
    schema_version = models.CharField(max_length=40, default="content-labels-v1")
    status = models.CharField(max_length=20, default="pending")
    reason = models.CharField(max_length=200, blank=True, default="")
    output = models.JSONField(default=dict)
    input_hash = models.CharField(max_length=64)
    elapsed_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField()


class ContentFeatureValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(PeerMedia, on_delete=models.CASCADE, related_name="content_features")
    feature_key = models.CharField(max_length=80)
    feature_version = models.CharField(max_length=20, default="1")
    value_json = models.JSONField(default=dict)
    review_state = models.CharField(max_length=20, default="suggested")
    review_revision = models.PositiveIntegerField(default=1)
    support = models.JSONField(default=list)
    origin = models.CharField(max_length=40, default="extraction")
    source_run = models.ForeignKey(
        ContentAnalysisRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="feature_values"
    )
    created_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["post", "feature_key", "review_state"])]


class ContentEmbedding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(PeerMedia, on_delete=models.CASCADE, related_name="embeddings")
    asset = models.ForeignKey(MediaAsset, null=True, blank=True, on_delete=models.CASCADE, related_name="embeddings")
    encoder_version = models.CharField(max_length=80)
    dimensions = models.PositiveIntegerField()
    vector_blob = models.BinaryField()
    vector_hash = models.CharField(max_length=64)
    frame_role = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField()


class InspirationRequestRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schema_version = models.CharField(max_length=40, default="inspiration-request-v1")
    fingerprint = models.CharField(max_length=64, unique=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField()


class InspirationRecommendationRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(InspirationRequestRecord, on_delete=models.CASCADE, related_name="runs")
    policy_version = models.CharField(max_length=40, default="inspiration-rank-v1")
    request_fingerprint = models.CharField(max_length=64)
    candidates = models.JSONField(default=list)
    excluded = models.JSONField(default=list)
    gaps = models.JSONField(default=list)
    created_at = models.DateTimeField()


class RecommendationExposure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(InspirationRecommendationRun, null=True, blank=True, on_delete=models.SET_NULL)
    reference = models.ForeignKey(InspirationReference, null=True, blank=True, on_delete=models.CASCADE)
    peer_media = models.ForeignKey(PeerMedia, null=True, blank=True, on_delete=models.CASCADE, related_name="exposures")
    event = models.CharField(max_length=20)
    position = models.PositiveIntegerField(null=True)
    note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField()


class ActivityReference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey("campaigns.Activity", on_delete=models.CASCADE, related_name="reference_links")
    reference = models.ForeignKey(InspirationReference, on_delete=models.CASCADE, related_name="activity_links")
    origin = models.CharField(max_length=40, default="owner_attach")
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField()
    reference_version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["activity", "reference"], name="unique_activity_reference")]


class ReviewedContextItem(models.Model):
    MEANING = [(s, s) for s in ["unknown", "confirmed", "corrected", "rejected"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_label = models.CharField(max_length=200)
    raw_text = models.TextField()
    meaning_state = models.CharField(max_length=12, choices=MEANING, default="unknown")
    reviewed_at = models.DateTimeField(null=True)
    notes = models.TextField(blank=True, default="")
