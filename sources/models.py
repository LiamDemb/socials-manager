import uuid

from django.db import models
from django.db.models import Q

from catalogue.models import Entity

PURPOSES = ["collect", "store", "display", "descriptive_derive", "statistical_fit", "model_infer", "llm_ingest", "export"]


class Source(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=40)
    route = models.CharField(max_length=40)
    label = models.CharField(max_length=200)
    account_entity = models.ForeignKey(Entity, null=True, blank=True, on_delete=models.PROTECT)
    url = models.URLField(blank=True, default="")
    secret_ref = models.CharField(max_length=120, blank=True, default="")
    fixture_class = models.CharField(max_length=10, default="owner")
    state = models.CharField(max_length=20, default="active")
    capability = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "route"], name="unique_provider_route")]


class SourcePolicyVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="policies")
    version = models.PositiveIntegerField()
    purposes = models.JSONField()
    conditions = models.TextField(blank=True, default="")
    assessment_ref = models.TextField()
    effective_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True)
    retention = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source", "version"], name="unique_policy_version")]
        ordering = ["-version"]

    def allows(self, purpose):
        return self.purposes.get(purpose) == "allowed"


class RawFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sha256 = models.CharField(max_length=64, unique=True)
    relative_path = models.CharField(max_length=200, unique=True)
    first_name = models.CharField(max_length=255)
    size_bytes = models.PositiveIntegerField()
    received_at = models.DateTimeField()


class MetricDefinition(models.Model):
    KINDS = [
        ("flow", "Daily flow"),
        ("stock", "Stock snapshot"),
        ("rolling_stock", "Rolling 28-day snapshot"),
        ("nested_stock", "Nested rolling subset"),
        ("daily_unique", "Daily unique count"),
        ("cumulative", "Cumulative snapshot"),
    ]
    id = models.CharField(max_length=80, primary_key=True)
    provider = models.CharField(max_length=40)
    code = models.CharField(max_length=60)
    version = models.PositiveIntegerField()
    label = models.CharField(max_length=120)
    unit = models.CharField(max_length=20, default="count")
    grain = models.CharField(max_length=20)
    kind = models.CharField(max_length=20, choices=KINDS)
    scope_kind = models.CharField(max_length=12)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    definition = models.TextField()
    outcome_modes = models.JSONField(default=list)
    csv_column = models.CharField(max_length=60, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "code", "version"], name="unique_metric_version")]


class ImportBatch(models.Model):
    STATES = [(s, s) for s in ["staged", "invalid", "committed", "rejected", "undone"]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="batches")
    policy_version = models.ForeignKey(SourcePolicyVersion, on_delete=models.PROTECT)
    raw_file = models.ForeignKey(RawFile, on_delete=models.PROTECT, related_name="batches")
    original_name = models.CharField(max_length=255)
    scope = models.CharField(max_length=12, blank=True, default="")
    mapped_entity = models.ForeignKey(Entity, null=True, blank=True, on_delete=models.PROTECT)
    parser_version = models.CharField(max_length=40)
    state = models.CharField(max_length=12, choices=STATES, default="staged")
    preview_revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField()
    committed_at = models.DateTimeField(null=True)
    undone_at = models.DateTimeField(null=True)
    undo_reason = models.TextField(blank=True, default="")
    summary = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]


class StagedObservation(models.Model):
    CLASSES = [(s, s) for s in ["new", "equal", "conflict"]]
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="staged")
    row_number = models.PositiveIntegerField()
    metric = models.ForeignKey(MetricDefinition, on_delete=models.PROTECT)
    period_start = models.DateField()
    value = models.BigIntegerField()
    classification = models.CharField(max_length=10, choices=CLASSES, default="new")
    existing_version = models.ForeignKey("ObservationVersion", null=True, on_delete=models.SET_NULL)
    approved = models.BooleanField(default=False)
    approval_reason = models.TextField(blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["batch", "metric", "period_start"], name="unique_staged_key")]


class StagedIssue(models.Model):
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="issues")
    row_number = models.PositiveIntegerField(null=True)
    column = models.CharField(max_length=60, blank=True, default="")
    code = models.CharField(max_length=40)
    message = models.CharField(max_length=300)


class Observation(models.Model):
    """Logical fact key. Values live in versions; the active version is recomputed from contributions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(Source, on_delete=models.PROTECT)
    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="observations")
    metric = models.ForeignKey(MetricDefinition, on_delete=models.PROTECT)
    period_start = models.DateField()
    period_end = models.DateField()
    dimension_key = models.CharField(max_length=120, blank=True, default="")
    active_version = models.ForeignKey("ObservationVersion", null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "entity", "metric", "period_start", "period_end", "dimension_key"], name="unique_observation_key"),
            models.CheckConstraint(condition=Q(period_end__gt=models.F("period_start")), name="observation_half_open"),
        ]
        indexes = [models.Index(fields=["entity", "metric", "period_start"])]


class ObservationVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    observation = models.ForeignKey(Observation, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    value = models.BigIntegerField(null=True)
    missing_reason = models.CharField(max_length=40, blank=True, default="")
    observed_at = models.DateTimeField(null=True)
    available_at = models.DateTimeField()
    policy_version = models.ForeignKey(SourcePolicyVersion, on_delete=models.PROTECT)
    source_row_ref = models.CharField(max_length=200)
    supersedes = models.ForeignKey("self", null=True, on_delete=models.PROTECT)
    revision_reason = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["observation", "version"], name="unique_observation_version"),
            models.CheckConstraint(
                condition=(Q(value__isnull=False) & Q(missing_reason="")) | (Q(value__isnull=True) & ~Q(missing_reason="")),
                name="value_xor_missing",
            ),
            models.CheckConstraint(condition=Q(value__isnull=True) | Q(value__gte=0), name="count_non_negative"),
        ]
        indexes = [models.Index(fields=["available_at"])]


class ObservationContribution(models.Model):
    version = models.ForeignKey(ObservationVersion, on_delete=models.PROTECT, related_name="contributions")
    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="contributions")
    active = models.BooleanField(default=True)
    row_ref = models.CharField(max_length=200)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["version", "batch"], name="unique_contribution")]
